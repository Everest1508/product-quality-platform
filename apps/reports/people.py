"""Attendance, leave and daily status reports. All owner/admin only: they are about named people."""

import statistics
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Max, Sum
from django.utils import timezone

from apps.accounts.models import Membership
from apps.attendance import service as att
from apps.attendance.models import AttendanceCorrection, AttendanceRecord
from apps.dashboards.models import ActivityLog
from apps.dsr.models import DSREntry
from apps.leave import service as leave
from apps.leave.models import LeaveRequest
from apps.payroll.service import holiday_dates

from .registry import Result, report
from .work import _bounds, _name


def _members(ctx):
    qs = Membership.objects.filter(company=ctx.company).select_related("user").order_by("user__username")
    return qs.filter(user=ctx.person) if ctx.person else qs


@report("lateness", "Lateness and penalties", "people", "Who arrived late, how often, by how many minutes, and what it cost.",
        "RPT-064", icon="clock", admin=True, filters=("period", "person"))
def lateness(ctx):
    shift = att.shift_for(ctx.company)
    exempt = set(Membership.objects.filter(company=ctx.company, late_exempt=True).values_list("user_id", flat=True))
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), check_in__isnull=False)
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    per = defaultdict(lambda: {"days": 0, "late": 0, "mins": 0, "money": Decimal("0"), "half": 0})
    users = {}
    for r in qs.select_related("user"):
        users[r.user_id] = r.user
        d = per[r.user_id]
        d["days"] += 1
        m = att.lateness_for(r, shift)
        if not m:
            continue
        d["late"] += 1
        d["mins"] += m
        pen = att.late_penalty_for(r, shift)
        if pen:
            d["money"] += Decimal(pen["amount"])
            d["half"] += pen["band"] == "half_day"
    rows = [[_name(users[u]), d["days"], d["late"], d["mins"], round(d["mins"] / d["late"]) if d["late"] else 0,
             d["half"], float(d["money"]), "Yes" if u in exempt else ""] for u, d in per.items()]
    rows.sort(key=lambda r: -r[3])
    return Result(["Person", "Days present", "Late days", "Total minutes late", "Average minutes late", "Half-day cuts",
                   f"Penalty ({shift.penalty_currency})", "Exempt from lateness"], rows,
                  [("Late days", f"{sum(r[2] for r in rows):,}"), ("Penalties", f"{sum(r[6] for r in rows):,.0f} {shift.penalty_currency}")],
                  "Worked out from check-in times and the shift rules, the same way payroll does.")


@report("unclosed-days", "Days with no check-out", "people", "Days someone checked in and never checked out, and whether a correction is pending.",
        "RPT-067", icon="triangle-alert", admin=True, filters=("period", "person"))
def unclosed_days(ctx):
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), date__lt=ctx.today,
                                         check_in__isnull=False, check_out__isnull=True).select_related("user").order_by("-date")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    pending = set(AttendanceCorrection.objects.filter(company=ctx.company, status="pending").values_list("user_id", "date"))
    rows = [[_name(r.user), r.date, r.check_in, (ctx.today - r.date).days, "Yes" if (r.user_id, r.date) in pending else "No"] for r in qs]
    return Result(["Person", "Date", "Checked in", "Days ago", "Correction pending"], rows,
                  [("Open days", f"{len(rows):,}"), ("People", f"{len({r[0] for r in rows}):,}")])


@report("attendance-edits", "Manual attendance edits", "people", "Who edited attendance by hand, when, and what they did.",
        "RPT-068", icon="eye", admin=True, filters=("period", "person"))
def attendance_edits(ctx):
    a, b = _bounds(ctx)
    qs = ActivityLog.objects.filter(company=ctx.company, event_type="attendance_edited", created_at__range=(a, b)).select_related("actor")
    rows = [[e.created_at, _name(e.actor) if e.actor else "Unknown", e.title, e.description] for e in qs.order_by("-created_at")]
    edited = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), is_edited=True).count()
    return Result(["When", "Edited by", "What", "Details"], rows,
                  [("Edit events", f"{len(rows):,}"), ("Days marked as edited", f"{edited:,}")],
                  "Direct admin edits do not keep the old times; approved corrections do (see the correction queue).")


@report("leave-balances", "Leave balance register", "people", "For every person and leave type: allowed, used, pending and left.",
        "RPT-074", icon="plane", admin=True, filters=("period", "person"))
def leave_balances(ctx):
    year = ctx.end.year
    policies = leave.policies_for(ctx.company)
    unpaid = dict(((u, p), v) for u, p, v in LeaveRequest.objects.filter(
        company=ctx.company, status="approved", start_date__year=year).values_list("user", "policy").annotate(s=Sum("unpaid_days")))
    rows = []
    for m in _members(ctx):
        for p in policies:
            b = leave.balance_for(ctx.company, m.user, p, year)
            rows.append([_name(m.user), p.name, "Unlimited" if b["is_unlimited"] else b["limit"], b["approved"], b["pending"],
                         "Unlimited" if b["is_unlimited"] else b["remaining"], unpaid.get((m.user_id, p.pk), 0)])
    return Result(["Person", "Leave type", "Paid days allowed", "Paid days used", "Pending", "Paid days left", "Unpaid days taken"], rows,
                  [("Year", str(year))], "Uses the calendar year of the end date.")


@report("dsr-compliance", "Daily status report compliance", "projects", "Who missed filing a DSR on a working day.",
        "RPT-080", icon="file-text", admin=True, filters=("period", "person"))
def dsr_compliance(ctx):
    shift = att.shift_for(ctx.company)
    last = min(ctx.end, ctx.today)
    holidays = holiday_dates(ctx.company, ctx.start, last)
    days = [ctx.start + timedelta(n) for n in range((last - ctx.start).days + 1)]
    days = [d for d in days if not shift.is_weekly_off(d) and d not in holidays]
    on_leave = leave.approved_leave_map(ctx.company, ctx.start, last)
    filed = defaultdict(set)
    for u, d in DSREntry.objects.filter(company=ctx.company, date__range=(ctx.start, last)).values_list("user", "date"):
        filed[u].add(d)
    users = set(DSREntry.objects.filter(company=ctx.company, date__gte=ctx.start - timedelta(days=90), date__lte=last).values_list("user", flat=True))
    rows = []
    for m in _members(ctx):
        if m.user_id not in users:
            continue
        due = [d for d in days if d not in on_leave.get(m.user_id, set())]
        missing = [d for d in due if d not in filed[m.user_id]]
        rows.append([_name(m.user), len(due), len(due) - len(missing), len(missing),
                     round((len(due) - len(missing)) * 100 / len(due)) if due else None,
                     ", ".join(f"{d.day} {d:%b}" for d in missing[:10]) + (" …" if len(missing) > 10 else "")])
    rows.sort(key=lambda r: -r[3])
    return Result(["Person", "Working days", "Days with a DSR", "Days missed", "Filed %", "Missed dates"], rows,
                  [("Days missed", f"{sum(r[3] for r in rows):,}")],
                  "Counts people who filed a DSR in the last 90 days. Weekly offs, company holidays and approved leave are skipped.")


@report("project-hours", "Hours by project and person", "projects", "Who spent how many hours on which project, from the DSR.",
        "RPT-035", icon="clock", admin=True, filters=("period", "product", "person"))
def project_hours(ctx):
    qs = DSREntry.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end))
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    agg = qs.values("product__name", "user__first_name", "user__last_name", "user__username").annotate(h=Sum("hours_spent"), n=Count("id"))
    tot = defaultdict(Decimal)
    for r in agg:
        tot[r["product__name"]] += r["h"] or 0
    rows = []
    for r in agg:
        who = f"{r['user__first_name']} {r['user__last_name']}".strip() or r["user__username"]
        p = r["product__name"] or "No project"
        h = r["h"] or Decimal("0")
        rows.append([p, who, float(h), round(float(h) * 100 / float(tot[r["product__name"]]), 1) if tot[r["product__name"]] else None, r["n"]])
    rows.sort(key=lambda r: (r[0], -r[2]))
    return Result(["Project", "Person", "Hours", "Share of project %", "Entries"], rows,
                  [("Total hours", f"{sum(r[2] for r in rows):,.1f}")])

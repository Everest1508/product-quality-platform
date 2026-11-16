"""Batch 2: attendance, leave and daily status reports. Owner/admin only."""

import statistics
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.accounts.models import Membership
from apps.attendance import service as att
from apps.attendance.models import AttendanceRecord
from apps.dsr.models import DSREntry
from apps.leave import service as leave
from apps.leave.models import LeaveRequest
from apps.payroll.models import PayrollProfile
from apps.payroll.service import effective_rate, holiday_dates

from .people import _members
from .registry import Result, report
from .work import _bounds, _name


def _working_days(ctx):
    shift = att.shift_for(ctx.company)
    last = min(ctx.end, ctx.today)
    hol = holiday_dates(ctx.company, ctx.start, last)
    return last, [d for d in (ctx.start + timedelta(n) for n in range((last - ctx.start).days + 1)) if not shift.is_weekly_off(d) and d not in hol]


@report("overtime", "Overtime and short days", "people", "Net hours worked against the standard day, per person.",
        "RPT-066", icon="clock", admin=True, filters=("period", "person"))
def overtime(ctx):
    shift = att.shift_for(ctx.company)
    std = shift.worked_minutes_per_day
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), check_in__isnull=False, check_out__isnull=False).select_related("user")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    per = defaultdict(lambda: {"u": None, "d": 0, "net": 0, "ot": 0, "short": 0, "lack": 0})
    for r in qs:
        if shift.is_weekly_off(r.date):
            continue
        n = att.net_minutes_for(r, shift)
        d = per[r.user_id]
        d["u"], d["d"], d["net"] = r.user, d["d"] + 1, d["net"] + n
        d["ot"] += max(0, n - std)
        if n < std - 30:
            d["short"] += 1
            d["lack"] += std - n
    rows = sorted(([_name(d["u"]), d["d"], round(d["net"] / d["d"] / 60, 2), round(d["ot"] / 60, 1), d["short"], round(d["lack"] / 60, 1)] for d in per.values()), key=lambda r: -r[3])
    return Result(["Person", "Full days", "Average net hours a day", "Overtime hours", "Short days (30+ min under)", "Hours short"], rows,
                  [("Standard day", f"{std / 60:.2f} h")], "Net hours take the unpaid break off. Weekly offs are skipped.")


@report("absenteeism", "Absence without leave", "people", "Working days nobody checked in and had no approved leave, with weekday patterns.",
        "RPT-070", icon="eye-off", admin=True, filters=("period", "person"))
def absenteeism(ctx):
    last, days = _working_days(ctx)
    on_leave = leave.approved_leave_map(ctx.company, ctx.start, last)
    present = defaultdict(set)
    for u, d in AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, last), check_in__isnull=False).values_list("user", "date"):
        present[u].add(d)
    known = set(AttendanceRecord.objects.filter(company=ctx.company, date__gte=ctx.start - timedelta(days=90), date__lte=last).values_list("user", flat=True))
    rows = []
    for m in _members(ctx):
        if m.user_id not in known:
            continue
        lv = on_leave.get(m.user_id, set())
        absent = [d for d in days if d not in present[m.user_id] and d not in lv]
        rows.append([_name(m.user), len(days), len(present[m.user_id] & set(days)), len([d for d in days if d in lv]), len(absent),
                     round(len(absent) * 100 / len(days), 1) if days else None, sum(d.weekday() == 0 for d in absent), sum(d.weekday() == 4 for d in absent)])
    rows.sort(key=lambda r: -r[4])
    return Result(["Person", "Working days", "Days present", "Days on leave", "Days absent", "Absent %", "Absent on Mondays", "Absent on Fridays"], rows,
                  [("Absent days", f"{sum(r[4] for r in rows):,}")], "Counts people with attendance in the last 90 days. Weekly offs, holidays and approved leave are skipped.")


@report("attendance-vs-dsr", "Hours punched vs hours logged", "people", "Whether the time people are in matches the time they log on work.",
        "RPT-072", icon="file-text", admin=True, filters=("period", "person"))
def attendance_vs_dsr(ctx):
    shift = att.shift_for(ctx.company)
    punched, pdays = defaultdict(int), defaultdict(set)
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), check_in__isnull=False, check_out__isnull=False)
    for r in qs:
        punched[r.user_id] += att.net_minutes_for(r, shift)
        pdays[r.user_id].add(r.date)
    logged, ldays = defaultdict(Decimal), defaultdict(set)
    for u, d, h in DSREntry.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end)).values_list("user", "date", "hours_spent"):
        logged[u] += h or 0
        ldays[u].add(d)
    rows = []
    for m in _members(ctx):
        u = m.user_id
        if u not in punched and u not in logged:
            continue
        ph, lh = punched[u] / 60, float(logged[u])
        rows.append([_name(m.user), round(ph, 1), round(lh, 1), round(lh * 100 / ph) if ph else None, len(pdays[u] - ldays[u]), len(ldays[u] - pdays[u])])
    rows.sort(key=lambda r: (r[3] is None, r[3]))
    return Result(["Person", "Net hours punched", "Hours logged in DSR", "Logged as % of punched", "Days punched with no DSR", "Days with DSR but no punch"], rows,
                  [("Punched", f"{sum(r[1] for r in rows):,.0f} h"), ("Logged", f"{sum(r[2] for r in rows):,.0f} h")])


@report("unpaid-leave-cost", "Unpaid leave cost", "people", "Unpaid leave days taken and the pay they saved.",
        "RPT-076", icon="banknote", admin=True, filters=("period", "person"))
def unpaid_leave_cost(ctx):
    qs = LeaveRequest.objects.filter(company=ctx.company, status="approved", unpaid_days__gt=0, start_date__range=(ctx.start, ctx.end)).select_related("user", "policy").order_by("start_date")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    profiles = defaultdict(list)
    for p in PayrollProfile.objects.filter(company=ctx.company).order_by("-effective_from"):
        profiles[p.user_id].append(p)
    rows, total = [], Decimal("0")
    for r in qs:
        p = next((x for x in profiles[r.user_id] if x.effective_from <= r.start_date), None)
        rate = effective_rate(ctx.company, p, r.start_date) if p else None
        cost = (rate * r.unpaid_days).quantize(Decimal("0.01")) if rate is not None else None
        total += cost or 0
        rows.append([_name(r.user), r.policy.name, r.start_date, r.end_date, float(r.unpaid_days), float(rate) if rate is not None else None, float(cost) if cost is not None else None])
    return Result(["Person", "Leave type", "From", "To", "Unpaid days", "Daily rate", "Pay not paid"], rows,
                  [("Unpaid days", f"{sum(r[4] for r in rows):,.1f}"), ("Pay saved", f"{total:,.2f}")], "Rate comes from the person's payroll profile on the first day of leave.")


@report("leave-decisions", "Leave approval speed", "people", "How fast leave requests get decided, and how each approver decides.",
        "RPT-077", icon="plane", admin=True, filters=("period",))
def leave_decisions(ctx):
    a, b = _bounds(ctx)
    per = defaultdict(lambda: {"n": 0, "ok": 0, "no": 0, "h": []})
    for r in LeaveRequest.objects.filter(company=ctx.company, decided_at__range=(a, b)).select_related("decided_by"):
        d = per[_name(r.decided_by) if r.decided_by else "Unknown"]
        d["n"] += 1
        d["ok"] += r.status == "approved"
        d["no"] += r.status == "rejected"
        d["h"].append((r.decided_at - r.created_at).total_seconds() / 3600)
    rows = [[k, d["n"], d["ok"], d["no"], round(statistics.median(d["h"]), 1), round(max(d["h"]), 1)] for k, d in sorted(per.items(), key=lambda x: -x[1]["n"])]
    waiting = LeaveRequest.objects.filter(company=ctx.company, status="pending").count()
    return Result(["Decided by", "Decided", "Approved", "Rejected", "Median hours to decide", "Slowest (hours)"], rows,
                  [("Decided", f"{sum(r[1] for r in rows):,}"), ("Waiting now", f"{waiting:,}")])


@report("work-mix", "Where the time goes", "projects", "Hours by type of work from the DSR: features, bug fixes, reviews, meetings, admin.",
        "RPT-081", icon="layout-dashboard", admin=True, filters=("period", "product", "person"))
def work_mix(ctx):
    qs = DSREntry.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end))
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    labels = dict(DSREntry.Category.choices)
    agg = {r["category"]: r for r in qs.values("category").annotate(h=Sum("hours_spent"))}
    total = sum(float(r["h"] or 0) for r in agg.values())
    rows = []
    for c, r in sorted(agg.items(), key=lambda x: -(x[1]["h"] or 0)):
        h = float(r["h"] or 0)
        rows.append([labels.get(c, c), round(h, 1), round(h * 100 / total, 1) if total else None, qs.filter(category=c).count(), qs.filter(category=c).values("user").distinct().count()])
    over = sum(float(agg[c]["h"] or 0) for c in ("meeting", "administration") if c in agg)
    return Result(["Type of work", "Hours", "Share %", "Entries", "People"], rows,
                  [("Hours", f"{total:,.1f}"), ("Meetings and admin", f"{round(over * 100 / total)}%" if total else "—")])


@report("dsr-quality", "DSR data quality", "projects", "Entries with no hours, auto-made entries, and hours far from the time the ticket took.",
        "RPT-082", icon="triangle-alert", admin=True, filters=("period", "person"))
def dsr_quality(ctx):
    qs = DSREntry.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end)).select_related("user")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    per = defaultdict(lambda: [None, 0, 0, 0, 0, 0])
    for e in qs:
        d = per[e.user_id]
        d[0] = e.user
        d[1] += 1
        d[2] += e.is_auto_logged
        d[3] += e.hours_spent == 0
        d[4] += e.unverified
        d[5] += bool(e.elapsed_hours and e.hours_spent and abs(float(e.hours_spent) - float(e.elapsed_hours)) > 2)
    rows = sorted(([_name(d[0]), d[1], d[2], d[3], d[4], d[5]] for d in per.values()), key=lambda r: -r[3])
    return Result(["Person", "Entries", "Auto-logged", "No hours entered", "Typed by hand through the MCP", "Hours differ from elapsed by 2h+"], rows,
                  [("Entries", f"{sum(r[1] for r in rows):,}"), ("No hours", f"{sum(r[3] for r in rows):,}")])


@report("dsr-blocked", "Blocked work", "projects", "Tasks people logged as blocked.",
        "RPT-084", icon="triangle-alert", admin=True, filters=("period", "product", "person"))
def dsr_blocked(ctx):
    qs = DSREntry.objects.filter(company=ctx.company, status="blocked", date__range=(ctx.start, ctx.end)).select_related("user", "product").order_by("-date")
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    rows = [[e.date, _name(e.user), e.product.name if e.product else "No project", e.task_name, float(e.hours_spent or 0), e.notes] for e in qs]
    return Result(["Date", "Person", "Project", "Task", "Hours", "Notes"], rows, [("Blocked entries", f"{len(rows):,}")])

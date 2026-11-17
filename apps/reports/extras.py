"""Batch 3: leads, quotes, attendance patterns, leave, forecasts and the client support summary."""

import re
import statistics
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Membership
from apps.attendance import service as att
from apps.attendance.models import AttendanceRecord
from apps.costing.models import Estimate
from apps.costing.views import compute as quote_compute
from apps.dashboards.models import ActivityLog
from apps.ingestion.models import ErrorGroup
from apps.leads.models import Lead
from apps.leave.models import LeaveRequest
from apps.payroll.models import Holiday, PayrollProfile
from apps.payroll.service import holiday_dates
from apps.products.models import ProductVersion
from apps.leave import service as leave

from .people import _members
from .registry import Result, report
from .work import CLOSED, _bounds, _name, _tickets

H = 3600


@report("lead-duplicates", "Repeat and duplicate leads", "customers", "The same email or phone number submitted more than once.",
        "RPT-048", icon="users", admin=True, filters=("period",))
def lead_duplicates(ctx):
    a, b = _bounds(ctx)
    groups = defaultdict(list)
    for l in Lead.objects.filter(company=ctx.company, created_at__range=(a, b)).order_by("created_at"):
        groups[("Email", l.email.strip().lower())].append(l)
        phone = re.sub(r"\D", "", l.phone)[-10:]
        if len(phone) >= 7:
            groups[("Phone", phone)].append(l)
    rows = [[k, v, len(ls), ", ".join(sorted({l.full_name for l in ls})), ls[0].created_at, ls[-1].created_at, ", ".join(sorted({l.get_status_display() for l in ls}))]
            for (k, v), ls in groups.items() if len(ls) > 1]
    rows.sort(key=lambda r: -r[2])
    return Result(["Matched on", "Value", "Times submitted", "Names used", "First", "Latest", "Statuses"], rows, [("Repeat contacts", f"{len(rows):,}")])


@report("arrival-pattern", "Arrival pattern by weekday", "people", "Average minutes after shift start each person arrives, per weekday.",
        "RPT-065", icon="calendar-days", admin=True, filters=("period", "person"))
def arrival_pattern(ctx):
    shift = att.shift_for(ctx.company)
    start = shift.start_time.hour * 60 + shift.start_time.minute
    per = defaultdict(lambda: defaultdict(list))
    users = {}
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), check_in__isnull=False).select_related("user")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    for r in qs:
        if shift.is_weekly_off(r.date):
            continue
        t = timezone.localtime(r.check_in)
        per[r.user_id][r.date.weekday()].append(t.hour * 60 + t.minute - start)
        users[r.user_id] = r.user
    rows = []
    for u, d in per.items():
        allm = [x for v in d.values() for x in v]
        rows.append([_name(users[u]), len(allm), *[round(sum(d[i]) / len(d[i])) if d.get(i) else None for i in range(5)], round(statistics.median(allm))])
    rows.sort(key=lambda r: -r[7])
    return Result(["Person", "Days", "Mon", "Tue", "Wed", "Thu", "Fri", "Median overall"], rows,
                  [("Shift starts", f"{shift.start_time:%I:%M %p}")], "Minutes after shift start; negative means earlier than the start. Weekly offs are skipped.")


@report("off-day-work", "Work on weekly offs and holidays", "people", "Who came in on a weekly off or company holiday.",
        "RPT-071", icon="calendar-days", admin=True, filters=("period", "person"))
def off_day_work(ctx):
    shift = att.shift_for(ctx.company)
    hol = dict(Holiday.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end)).values_list("date", "name"))
    qs = AttendanceRecord.objects.filter(company=ctx.company, date__range=(ctx.start, ctx.end), check_in__isnull=False).select_related("user").order_by("-date")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    rows = []
    for r in qs:
        why = hol.get(r.date) and f"Holiday: {hol[r.date]}" or ("Weekly off" if shift.is_weekly_off(r.date) else "")
        if why:
            rows.append([_name(r.user), r.date, f"{r.date:%A}", why, r.check_in, r.check_out, round(att.net_minutes_for(r, shift) / 60, 2) if r.check_out else None])
    return Result(["Person", "Date", "Day", "Why it is off", "Checked in", "Checked out", "Net hours"], rows, [("Days worked off", f"{len(rows):,}")])


@report("leave-usage", "Leave taken by month and type", "people", "How much leave is taken, when, and of what kind.",
        "RPT-075", icon="plane", admin=True, filters=("period", "person"))
def leave_usage(ctx):
    qs = LeaveRequest.objects.filter(company=ctx.company, status="approved", start_date__range=(ctx.start, ctx.end)).select_related("policy")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    per = defaultdict(lambda: [0, Decimal(0), Decimal(0), set()])
    for r in qs:
        d = per[(f"{r.start_date:%Y-%m}", r.policy.name)]
        d[0] += 1
        d[1] += r.paid_days
        d[2] += r.unpaid_days
        d[3].add(r.user_id)
    rows = [[m, p, d[0], len(d[3]), float(d[1]), float(d[2]), float(d[1] + d[2])] for (m, p), d in sorted(per.items())]
    return Result(["Month", "Leave type", "Requests", "People", "Paid days", "Unpaid days", "Total days"], rows, [("Days", f"{sum(r[6] for r in rows):,.1f}")])


@report("leave-over-cap", "Leave split into paid and unpaid", "people", "Approved requests where part of the leave was charged as unpaid.",
        "RPT-078", icon="percent", admin=True, filters=("period", "person"))
def leave_over_cap(ctx):
    qs = LeaveRequest.objects.filter(company=ctx.company, status="approved", unpaid_days__gt=0, policy__is_paid=True,
                                     start_date__range=(ctx.start, ctx.end)).select_related("user", "policy", "decided_by").order_by("-start_date")
    if ctx.person:
        qs = qs.filter(user=ctx.person)
    rows = [[_name(r.user), r.policy.name, r.start_date, r.end_date, float(r.days), float(r.paid_days), float(r.unpaid_days), r.get_split_mode_display(),
             _name(r.decided_by) if r.decided_by else ""] for r in qs]
    return Result(["Person", "Leave type", "From", "To", "Days", "Paid", "Unpaid", "Split decided", "Approved by"], rows,
                  [("Requests", f"{len(rows):,}"), ("Set by hand", f"{sum(r[7] == 'Manual' for r in rows):,}")])


@report("capacity-outlook", "Who is available, next 30 days", "people", "Day by day: working day or not, people on leave and people available.",
        "RPT-079", icon="calendar-days", admin=True, filters=())
def capacity_outlook(ctx):
    shift = att.shift_for(ctx.company)
    end = ctx.today + timedelta(days=29)
    hol = dict(Holiday.objects.filter(company=ctx.company, date__range=(ctx.today, end)).values_list("date", "name"))
    cur = {}
    for p in PayrollProfile.objects.filter(company=ctx.company, effective_from__lte=ctx.today).order_by("user_id", "-effective_from"):
        cur.setdefault(p.user_id, p)
    staff = {u for u, p in cur.items() if p.is_on_payroll}
    ok, wait = defaultdict(set), defaultdict(set)
    for r in LeaveRequest.objects.filter(company=ctx.company, status__in=("approved", "pending"), start_date__lte=end, end_date__gte=ctx.today):
        for i in range((r.end_date - r.start_date).days + 1):
            d = r.start_date + timedelta(i)
            (ok if r.status == "approved" else wait)[d].add(r.user_id)
    rows = []
    for n in range(30):
        d = ctx.today + timedelta(n)
        off = shift.is_weekly_off(d) or d in hol
        away = len(ok[d] & staff)
        rows.append([d, f"{d:%A}", "No" if off else "Yes", hol.get(d, "Weekly off" if shift.is_weekly_off(d) else ""), None if off else away,
                     None if off else len(wait[d] & staff), None if off else len(staff) - away])
    return Result(["Date", "Day", "Working day", "Why not", "On approved leave", "Leave waiting for approval", "People available"], rows,
                  [("People on payroll", f"{len(staff):,}")])


@report("backlog-forecast", "Ticket backlog forecast", "tickets", "At the last four weeks' pace, how long the open backlog would take to clear.",
        "RPT-095", icon="chart-column", admin=True, filters=("product",))
def backlog_forecast(ctx):
    now = timezone.now()
    since = now - timedelta(days=28)
    per = defaultdict(lambda: [0, 0, 0])
    tq = _tickets(ctx)
    for t in tq:
        name = t.product.name if t.product else "No project"
        if t.status not in CLOSED:
            per[name][0] += 1
        if t.created_at >= since:
            per[name][1] += 1
    ids = {t.pk: (t.product.name if t.product else "No project") for t in tq}
    done = set()
    for tid, in ActivityLog.objects.filter(company=ctx.company, event_type="ticket_status_changed", created_at__gte=since, metadata__to__in=CLOSED, target_object_id__in=list(ids)).values_list("target_object_id"):
        if tid not in done:
            done.add(tid)
            per[ids[tid]][2] += 1
    rows = []
    for p, (open_, c, r) in sorted(per.items()):
        cw, rw = c / 4, r / 4
        net = rw - cw
        rows.append([p, open_, round(cw, 1), round(rw, 1), round(net, 1), round(open_ / net, 1) if net > 0 and open_ else ("Clear" if not open_ else "Growing")])
    return Result(["Project", "Open now", "Created per week", "Resolved per week", "Net burn per week", "Weeks to clear"], rows,
                  [("Open tickets", f"{sum(r[1] for r in rows):,}")], "Pace is the average of the last 28 days. Resolved counts come from the activity log.")


@report("client-support-summary", "Support and reliability summary", "projects", "Per project: tickets resolved, how fast, what is still open, errors fixed and releases shipped.",
        "RPT-099", icon="headset", filters=("period", "product"))
def client_support_summary(ctx):
    a, b = _bounds(ctx)
    tq = _tickets(ctx)
    per = defaultdict(lambda: {"res": [], "open": 0, "crit": 0})
    first = {}
    for tid, at in ActivityLog.objects.filter(company=ctx.company, event_type="ticket_status_changed", created_at__range=(a, b), metadata__to__in=CLOSED,
                                              target_object_id__in=tq.values("pk")).order_by("created_at").values_list("target_object_id", "created_at"):
        first.setdefault(tid, at)
    for t in tq:
        d = per[t.product.name if t.product else "No project"]
        if t.pk in first:
            d["res"].append((first[t.pk] - t.created_at).total_seconds() / H)
        if t.status not in CLOSED:
            d["open"] += 1
            d["crit"] += t.priority == "critical"
    eg = defaultdict(lambda: [0, 0])
    for g in ErrorGroup.objects.filter(company=ctx.company, product__in=ctx.products).select_related("product"):
        if ctx.product and g.product_id != ctx.product.pk:
            continue
        eg[g.product.name][1] += g.status in ("open", "investigating")
    rel = defaultdict(int)
    for v in ProductVersion.objects.filter(company=ctx.company, product__in=ctx.products, released_at__range=(a, b)).select_related("product"):
        if not ctx.product or v.product_id == ctx.product.pk:
            rel[v.product.name] += 1
    names = sorted(set(per) | set(eg) | set(rel))
    rows = [[n, len(per[n]["res"]), round(statistics.median(per[n]["res"]), 1) if per[n]["res"] else None, per[n]["open"], per[n]["crit"], eg[n][1], rel[n]] for n in names]
    return Result(["Project", "Tickets resolved", "Median hours to resolve", "Open tickets", "Open critical tickets", "Open errors", "Releases shipped"], rows,
                  [("Resolved", f"{sum(r[1] for r in rows):,}"), ("Releases", f"{sum(r[6] for r in rows):,}")])

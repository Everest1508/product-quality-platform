"""Batch 3: system health, adoption, ingestion, automation and data quality. Owner/admin only."""

import statistics
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Max, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.accounts.models import ExternalAccessToken, Membership
from apps.automation.models import AutoTicketLog, AutoTicketRule
from apps.dashboards.models import ActivityLog
from apps.feedback.models import Survey
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback, IngestedTicket
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.notifications.models import Notification, NotificationMute, PushSubscription
from apps.payroll.models import PayrollProfile
from apps.products.models import Product
from apps.tickets.models import Ticket

from .registry import Result, report
from .work import CLOSED, _bounds, _errors, _name

MODULES = [("Tickets", "ticket_"), ("Errors", "error_"), ("Leave and attendance", ("leave_", "attendance_")), ("Payroll", ("payroll_", "holiday_")),
           ("Projects", "project_"), ("Surveys and feedback", ("survey_", "feedback_"))]


@report("rule-effectiveness", "Automation rule effectiveness", "errors", "How often each rule fires, how many tickets it creates and whether they get resolved.",
        "RPT-012", icon="sparkles", admin=True, filters=("period", "product"))
def rule_effectiveness(ctx):
    a, b = _bounds(ctx)
    rules = AutoTicketRule.objects.filter(company=ctx.company, product__in=ctx.products).select_related("product")
    if ctx.product:
        rules = rules.filter(product=ctx.product)
    rows = []
    for r in rules:
        logs = AutoTicketLog.objects.filter(rule=r, created_at__range=(a, b)).select_related("ticket")
        tks = [l.ticket for l in logs if l.ticket]
        rows.append([r.name, r.product.name, r.get_trigger_type_display(), r.threshold_count, r.window_minutes, "On" if r.is_active else "Off", logs.count(), len(tks),
                     round(sum(t.status in CLOSED for t in tks) * 100 / len(tks)) if tks else None, r.trigger_count, r.last_triggered_at])
    return Result(["Rule", "Project", "Trigger", "Occurrence threshold", "Window (minutes)", "Active", "Fires in period", "Tickets created", "Of those resolved %", "Fires ever", "Last fired"], rows,
                  [("Rules", f"{len(rows):,}")])


@report("error-spikes", "Error spikes right now", "errors", "Error groups running far above their usual rate in the last 24 hours.",
        "RPT-023", icon="triangle-alert", admin=True, filters=("product",))
def error_spikes(ctx):
    now = timezone.now()
    groups = {g.pk: g for g in _errors(ctx)}
    day = dict(ErrorOccurrence.objects.filter(error_group__in=list(groups), created_at__gte=now - timedelta(hours=24)).values_list("error_group").annotate(n=Count("id")))
    base = dict(ErrorOccurrence.objects.filter(error_group__in=list(day), created_at__gte=now - timedelta(days=8), created_at__lt=now - timedelta(hours=24)).values_list("error_group").annotate(n=Count("id")))
    rows = []
    for gid, n in day.items():
        usual = base.get(gid, 0) / 7
        ratio = round(n / usual, 1) if usual else None
        if n >= 5 and (usual == 0 or n >= 3 * usual):
            g = groups[gid]
            rows.append([g.title, g.product.name, g.get_severity_display(), g.get_status_display(), n, round(usual, 1), ratio if ratio else "New or no history", g.last_seen])
    rows.sort(key=lambda r: -r[4])
    return Result(["Error", "Project", "Severity", "Status", "Occurrences, last 24h", "Usual per day (last 7 days)", "Times the usual", "Last seen"], rows,
                  [("Spiking", f"{len(rows):,}")], "Listed when there are 5+ in 24 hours and at least three times the usual daily count.")


@report("customer-impact", "Customers affected by errors", "errors", "Distinct end users who hit an error, per project and week.",
        "RPT-021", icon="users", admin=True, filters=("period", "product"))
def customer_impact(ctx):
    a, b = _bounds(ctx)
    per = defaultdict(lambda: [0, set(), set()])
    qs = ErrorOccurrence.objects.filter(company=ctx.company, error_group__in=_errors(ctx), created_at__range=(a, b)).annotate(w=TruncWeek("created_at")).values_list("w", "error_group__product__name", "user_ref", "error_group")
    for w, p, u, g in qs:
        d = per[(w.date(), p)]
        d[0] += 1
        d[2].add(g)
        if u:
            d[1].add(u)
    rows = [[w, p, len(d[1]), d[0], len(d[2]), round(d[0] / len(d[1]), 1) if d[1] else None] for (w, p), d in sorted(per.items())]
    return Result(["Week starting", "Project", "Distinct users affected", "Occurrences", "Error groups", "Occurrences per user"], rows,
                  note="Needs the SDK to send a user reference with each error.")


@report("survey-activity", "Survey activity", "customers", "Which surveys collect answers and which are quiet.",
        "RPT-027", icon="headset", admin=True, filters=("product",))
def survey_activity(ctx):
    now = timezone.now()
    qs = Survey.objects.filter(company=ctx.company, product__in=ctx.products).select_related("product").annotate(n=Count("responses"), last=Max("responses__created_at"))
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    rows = [[s.name, s.product.name, s.get_survey_type_display(), s.get_status_display(), s.created_at, s.n, s.last, (now - s.last).days if s.last else None,
             s.compute_avg_score(), "Active with no answers" if s.status == "active" and not s.n else ""] for s in qs]
    rows.sort(key=lambda r: (r[9] == "", -r[5]))
    return Result(["Survey", "Project", "Type", "Status", "Created", "Responses", "Last response", "Days since", "Average score", "Attention"], rows, [("Surveys", f"{len(rows):,}")])


@report("sdk-intake", "Tickets sent by apps", "customers", "Tickets customer apps pushed through the API, by project and type.",
        "RPT-029", icon="ticket", admin=True, filters=("period", "product"))
def sdk_intake(ctx):
    a, b = _bounds(ctx)
    qs = IngestedTicket.objects.filter(company=ctx.company, product__in=ctx.products, created_at__range=(a, b)).select_related("product")
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    per = defaultdict(lambda: [0, set(), None])
    for t in qs:
        d = per[(t.product.name, t.ticket_type)]
        d[0] += 1
        if t.user_ref:
            d[1].add(t.user_ref)
        d[2] = max(d[2], t.created_at) if d[2] else t.created_at
    rows = [[p, t, d[0], len(d[1]), d[2]] for (p, t), d in sorted(per.items())]
    return Result(["Project", "Type", "Tickets received", "Distinct reporters", "Latest"], rows, [("Received", f"{sum(r[2] for r in rows):,}")])

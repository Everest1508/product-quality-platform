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


@report("dormant-rules", "Rules that never fire", "errors", "Active automation rules that have not fired for 30 days or ever.",
        "RPT-094", icon="eye-off", admin=True, filters=())
def dormant_rules(ctx):
    now = timezone.now()
    rows = [[r.name, r.product.name, r.get_trigger_type_display(), r.created_at, r.last_triggered_at, (now - (r.last_triggered_at or r.created_at)).days]
            for r in AutoTicketRule.objects.filter(company=ctx.company, is_active=True).select_related("product")
            if not r.last_triggered_at or (now - r.last_triggered_at).days >= 30]
    rows.sort(key=lambda r: -r[5])
    return Result(["Rule", "Project", "Trigger", "Created", "Last fired", "Days since fired or created"], rows, [("Dormant rules", f"{len(rows):,}")])


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


@report("ingestion-volume", "Data received from apps", "audit", "How much each project's apps send us: errors, feedback and tickets per week.",
        "RPT-092", icon="chart-column", admin=True, filters=("period", "product"))
def ingestion_volume(ctx):
    a, b = _bounds(ctx)
    per = defaultdict(lambda: [0, 0, 0])
    pf = Q(error_group__product=ctx.product) if ctx.product else Q()
    for w, p, n in ErrorOccurrence.objects.filter(pf, company=ctx.company, created_at__range=(a, b)).annotate(w=TruncWeek("created_at")).values_list("w", "error_group__product__name").annotate(n=Count("id")):
        per[(w.date(), p)][0] += n
    ff = Q(product=ctx.product) if ctx.product else Q()
    for w, p, n in Feedback.objects.filter(ff, company=ctx.company, created_at__range=(a, b)).annotate(w=TruncWeek("created_at")).values_list("w", "product__name").annotate(n=Count("id")):
        per[(w.date(), p)][1] += n
    for w, p, n in IngestedTicket.objects.filter(ff, company=ctx.company, created_at__range=(a, b)).annotate(w=TruncWeek("created_at")).values_list("w", "product__name").annotate(n=Count("id")):
        per[(w.date(), p)][2] += n
    rows = [[w, p, *d, sum(d)] for (w, p), d in sorted(per.items())]
    return Result(["Week starting", "Project", "Error occurrences", "Feedback ratings", "Tickets", "Total records"], rows, [("Records", f"{sum(r[5] for r in rows):,}")])


@report("feature-adoption", "Who uses which part of the app", "audit", "Activity per person across tickets, errors, leave, payroll, projects and surveys.",
        "RPT-089", icon="layout-dashboard", admin=True, filters=("period", "person"))
def feature_adoption(ctx):
    a, b = _bounds(ctx)
    qs = ActivityLog.objects.filter(company=ctx.company, created_at__range=(a, b), actor__isnull=False).select_related("actor")
    if ctx.person:
        qs = qs.filter(actor=ctx.person)
    per = defaultdict(lambda: {"u": None, "m": defaultdict(int), "last": None})
    for e in qs:
        d = per[e.actor_id]
        d["u"] = e.actor
        label = next((n for n, pre in MODULES if e.event_type.startswith(pre)), "Other")
        d["m"][label] += 1
        d["last"] = max(d["last"], e.created_at) if d["last"] else e.created_at
    rows = [[_name(d["u"]), *[d["m"][n] for n, _ in MODULES], d["m"]["Other"], sum(d["m"].values()), d["last"]] for d in per.values()]
    rows.sort(key=lambda r: -r[-2])
    return Result(["Person", *[n for n, _ in MODULES], "Other", "Total actions", "Last action"], rows, [("People active", f"{len(rows):,}")])


@report("notification-engagement", "Notification engagement", "audit", "Read rate and speed per kind of notification, and how many people muted each.",
        "RPT-090", icon="eye", admin=True, filters=("period",))
def notification_engagement(ctx):
    a, b = _bounds(ctx)
    labels = dict(Notification.Kind.choices)
    per = defaultdict(lambda: [0, 0, []])
    for k, c, r in Notification.objects.filter(company=ctx.company, created_at__range=(a, b)).values_list("kind", "created_at", "read_at"):
        d = per[k]
        d[0] += 1
        if r:
            d[1] += 1
            d[2].append((r - c).total_seconds() / 3600)
    muted = dict(NotificationMute.objects.values_list("kind").annotate(n=Count("id")))
    rows = [[labels.get(k, k), d[0], d[1], round(d[1] * 100 / d[0]), round(statistics.median(d[2]), 1) if d[2] else None, muted.get(k, 0)] for k, d in sorted(per.items(), key=lambda x: -x[1][0])]
    return Result(["Kind", "Sent", "Read", "Read %", "Median hours to read", "People who muted it"], rows,
                  [("Sent", f"{sum(r[1] for r in rows):,}"), ("People with push on", f"{PushSubscription.objects.values('user').distinct().count():,}")])


@report("sign-in-activity", "Sign-ins and app tokens", "audit", "Last sign-in per person, dormant accounts, and desktop-app tokens in use.",
        "RPT-088", icon="eye", admin=True, filters=())
def sign_in_activity(ctx):
    now = timezone.now()
    toks = defaultdict(list)
    for t in ExternalAccessToken.objects.filter(user__memberships__company=ctx.company, revoked_at__isnull=True):
        if not t.expires_at or t.expires_at > now:
            toks[t.user_id].append(t)
    rows = []
    for m in Membership.objects.filter(company=ctx.company).select_related("user").order_by("user__username"):
        u = m.user
        ts = toks[u.pk]
        used = max((t.last_used_at for t in ts if t.last_used_at), default=None)
        ip = next((t.last_used_ip for t in sorted(ts, key=lambda t: t.last_used_at or t.created_at, reverse=True) if t.last_used_ip), "")
        idle = (now - u.last_login).days if u.last_login else None
        rows.append([_name(u), m.get_role_display(), u.last_login, idle, len(ts), used, ip,
                     "Never signed in" if not u.last_login else "Dormant 30+ days" if idle >= 30 else ""])
    rows.sort(key=lambda r: (r[7] == "", -(r[3] or 9999)))
    return Result(["Person", "Role", "Last sign-in", "Days since", "Active app tokens", "Token last used", "Last token IP", "Attention"], rows,
                  [("Dormant or never", f"{sum(bool(r[7]) for r in rows):,}")], "Only the latest sign-in is stored, not a history.")


@report("data-health", "Data health check", "audit", "Gaps and inconsistencies across tickets, projects, people, payroll and leave.",
        "RPT-093", icon="circle-check", admin=True, filters=())
def data_health(ctx):
    c = ctx.company
    cur = {}
    for p in PayrollProfile.objects.filter(company=c, effective_from__lte=ctx.today).order_by("user_id", "-effective_from"):
        cur.setdefault(p.user_id, p)
    uses = set(LeaveRequest.objects.filter(company=c).values_list("policy", flat=True))

    def names(qs, n=5):
        qs = list(qs[:n + 1])
        return ", ".join(str(x) for x in qs[:n]) + (" …" if len(qs) > n else "")

    checks = [
        ("Tickets", "Tickets with no project", Ticket.objects.filter(company=c, product__isnull=True)),
        ("Tickets", "Open tickets with no owner", Ticket.objects.filter(company=c, assignees__isnull=True).exclude(status__in=CLOSED)),
        ("Projects", "Projects with no lead", Product.objects.filter(company=c, lead__isnull=True)),
        ("Projects", "Projects with no planned end date", Product.objects.filter(company=c, end_date__isnull=True)),
        ("Projects", "Projects with no server", Product.objects.filter(company=c, server__isnull=True)),
        ("Projects", "Projects with no one granted access", Product.objects.filter(company=c).annotate(n=Count("access_records")).filter(n=0)),
        ("Errors", "Open error groups older than 14 days", ErrorGroup.objects.filter(company=c, status="open", first_seen__lt=timezone.now() - timedelta(days=14))),
        ("People", "Members with no payroll profile", Membership.objects.filter(company=c).exclude(user_id__in=list(cur))),
        ("Payroll", "On payroll but no salary or rate", [p.user.username for p in cur.values() if p.is_on_payroll and not (p.monthly_salary or p.daily_rate)]),
        ("Leave", "Leave types nobody has used", LeavePolicy.objects.filter(company=c).exclude(pk__in=uses)),
        ("Surveys", "Active surveys with no answers", Survey.objects.filter(company=c, status="active").annotate(n=Count("responses")).filter(n=0)),
        ("Automation", "Active rules that never fired", AutoTicketRule.objects.filter(company=c, is_active=True, last_triggered_at__isnull=True)),
    ]
    rows = []
    for mod, label, qs in checks:
        n = len(qs) if isinstance(qs, list) else qs.distinct().count()
        rows.append([mod, label, n, "OK" if not n else "Check", ", ".join(qs[:5]) if isinstance(qs, list) else names(qs.distinct())])
    return Result(["Area", "Check", "Count", "Result", "First few"], rows,
                  [("Checks with a problem", f"{sum(r[3] == 'Check' for r in rows):,} of {len(rows)}")])

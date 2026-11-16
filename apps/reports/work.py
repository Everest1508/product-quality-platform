"""Tickets, errors, customer feedback, leads and projects."""

import statistics
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, Max, Min, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from apps.dashboards.models import ActivityLog
from apps.feedback.models import Survey, SurveyResponse
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback
from apps.leads.models import Lead
from apps.products.lifecycle import LABELS as STAGE_LABELS
from apps.products.models import CrunchItem, ProjectLogEntry
from apps.products.access import accessible_error_groups, accessible_tickets
from apps.tickets.models import Ticket

from .registry import Result, report

CLOSED = ("resolved", "closed")
SEVERITY = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _name(u):
    return (u.get_full_name() or u.username) if u else "Nobody"


def _tickets(ctx):
    qs = accessible_tickets(ctx.user, ctx.company).select_related("product", "created_by")
    return qs.filter(product=ctx.product) if ctx.product else qs


def _errors(ctx):
    qs = accessible_error_groups(ctx.user, ctx.company).select_related("product")
    return qs.filter(product=ctx.product) if ctx.product else qs


def _bounds(ctx):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(ctx.start, time.min), tz),
            timezone.make_aware(datetime.combine(ctx.end, time.max), tz))


def _assignees(t):
    names = [_name(u) for u in t.assignees.all()]
    return ", ".join(names) or "Nobody"


@report("ticket-register", "Ticket register", "tickets", "Every ticket in the period as a sheet you can sort and share.",
        "RPT-001", icon="ticket", filters=("period", "product"))
def ticket_register(ctx):
    a, b = _bounds(ctx)
    qs = _tickets(ctx).filter(created_at__range=(a, b)).prefetch_related("assignees").order_by("-created_at")
    rows = [[t.key, t.title, t.product.name if t.product else "No project", t.get_ticket_type_display(), t.get_status_display(),
             t.get_priority_display(), t.get_source_display(), _assignees(t), _name(t.created_by) if t.created_by else "",
             t.created_at, t.deadline, t.updated_at] for t in qs]
    return Result(["Ticket", "Title", "Project", "Type", "Status", "Priority", "Source", "Assigned to", "Created by",
                   "Created", "Deadline", "Last updated"], rows, [("Tickets", f"{len(rows):,}")])


@report("ticket-ageing", "Ticket ageing", "tickets", "How old the open backlog is, per project, in age bands.",
        "RPT-002", icon="clock", filters=("product",))
def ticket_ageing(ctx):
    now = timezone.now()
    bands = [(2, "0-2 days"), (7, "3-7 days"), (14, "8-14 days"), (30, "15-30 days"), (10**6, "Over 30 days")]
    per = defaultdict(lambda: {"n": [0] * len(bands), "ages": []})
    for t in _tickets(ctx).exclude(status__in=CLOSED):
        age = (now - t.created_at).days
        row = per[t.product.name if t.product else "No project"]
        row["n"][next(i for i, (lim, _) in enumerate(bands) if age <= lim)] += 1
        row["ages"].append(age)
    rows = [[p, *d["n"], sum(d["n"]), max(d["ages"]), int(statistics.median(d["ages"]))] for p, d in per.items()]
    rows.sort(key=lambda r: -r[6])
    total = sum(r[6] for r in rows)
    old = sum(r[5] for r in rows)
    return Result(["Project", *[b for _, b in bands], "Open tickets", "Oldest (days)", "Median age (days)"], rows,
                  [("Open tickets", f"{total:,}"), ("Older than 30 days", f"{old:,}")],
                  "Age counts from the day the ticket was created.")


@report("ticket-deadlines", "Overdue and due-soon tickets", "tickets", "Tickets past their deadline or due in the next 7 days, and who has them.",
        "RPT-003", icon="calendar-days", filters=("product", "person"))
def ticket_deadlines(ctx):
    now = timezone.now()
    qs = (_tickets(ctx).exclude(status__in=CLOSED).filter(deadline__isnull=False, deadline__lte=now + timedelta(days=7))
          .prefetch_related("assignees").order_by("deadline"))
    if ctx.person:
        qs = qs.filter(assignees=ctx.person)
    rows, late = [], 0
    for t in qs:
        days = (t.deadline - now).days
        late += t.deadline < now
        rows.append([t.key, t.title, t.product.name if t.product else "No project", t.get_priority_display(),
                     t.get_status_display(), _assignees(t), t.deadline,
                     f"{-days} day{'s' if days != -1 else ''} overdue" if t.deadline < now else (f"Due in {days} day{'s' if days != 1 else ''}" if days else "Due today")])
    return Result(["Ticket", "Title", "Project", "Priority", "Status", "Assigned to", "Deadline", "Where it stands"], rows,
                  [("Overdue", f"{late:,}"), ("Due in 7 days", f"{len(rows) - late:,}")])


@report("tickets-flow", "Created vs resolved, by week", "tickets", "Whether we close tickets as fast as they arrive.",
        "RPT-006", icon="chart-column", filters=("period", "product"))
def tickets_flow(ctx):
    a, b = _bounds(ctx)
    tq = _tickets(ctx)
    created = tq.filter(created_at__range=(a, b)).annotate(w=TruncWeek("created_at")).values("w").annotate(n=Count("id"))
    done = (ActivityLog.objects.filter(company=ctx.company, event_type="ticket_status_changed", created_at__range=(a, b),
                                       metadata__to__in=CLOSED, target_object_id__in=tq.values("pk"))
            .annotate(w=TruncWeek("created_at")).values("w").annotate(n=Count("target_object_id", distinct=True)))
    c, d = {r["w"].date(): r["n"] for r in created}, {r["w"].date(): r["n"] for r in done}
    rows = []
    for w in sorted(set(c) | set(d)):
        cn, dn = c.get(w, 0), d.get(w, 0)
        rows.append([w, cn, dn, cn - dn, round(dn * 100 / cn, 1) if cn else None])
    tc, td = sum(r[1] for r in rows), sum(r[2] for r in rows)
    return Result(["Week starting", "Created", "Resolved", "Backlog change", "Resolved per 100 created"], rows,
                  [("Created", f"{tc:,}"), ("Resolved", f"{td:,}"), ("Backlog change", f"{tc - td:+,}")],
                  "Resolved counts come from status changes recorded in the activity log.")


@report("ticket-stale", "Unassigned and stale tickets", "tickets", "Open tickets with no owner, or that nobody has touched for a week.",
        "RPT-009", icon="eye-off", filters=("product",))
def ticket_stale(ctx):
    now = timezone.now()
    rows = []
    for t in _tickets(ctx).exclude(status__in=CLOSED).prefetch_related("assignees").order_by("updated_at"):
        idle = (now - t.updated_at).days
        nobody = not t.assignees.all()
        if not (nobody or idle >= 7):
            continue
        why = "No owner and untouched" if nobody and idle >= 7 else ("No owner" if nobody else "Untouched for a week or more")
        rows.append([t.key, t.title, t.product.name if t.product else "No project", t.get_priority_display(),
                     t.get_status_display(), _assignees(t), t.updated_at, idle, why])
    rows.sort(key=lambda r: ({"Critical": 0, "High": 1, "Medium": 2, "Low": 3}[r[3]], -r[7]))
    return Result(["Ticket", "Title", "Project", "Priority", "Status", "Assigned to", "Last updated", "Days idle", "Why listed"], rows,
                  [("Listed", f"{len(rows):,}"), ("No owner", f"{sum(r[5] == 'Nobody' for r in rows):,}")])


@report("error-trend", "Error trend", "errors", "How many errors arrive per day or week, by severity.",
        "RPT-014", icon="triangle-alert", filters=("period", "product"))
def error_trend(ctx):
    a, b = _bounds(ctx)
    weekly = (ctx.end - ctx.start).days > 31
    trunc = TruncWeek if weekly else TruncDate
    groups = _errors(ctx)
    occ = (ErrorOccurrence.objects.filter(company=ctx.company, error_group__in=groups, created_at__range=(a, b))
           .annotate(d=trunc("created_at")).values("d", "error_group__severity").annotate(n=Count("id")))
    new = groups.filter(first_seen__range=(a, b)).annotate(d=trunc("first_seen")).values("d").annotate(n=Count("id"))
    per = defaultdict(lambda: dict.fromkeys(SEVERITY, 0))
    for r in occ:
        per[r["d"].date() if hasattr(r["d"], "date") else r["d"]][r["error_group__severity"]] += r["n"]
    fresh = {(r["d"].date() if hasattr(r["d"], "date") else r["d"]): r["n"] for r in new}
    rows = [[d, sum(v.values()), *v.values(), fresh.get(d, 0)] for d, v in sorted(per.items())]
    return Result([("Week starting" if weekly else "Day"), "Occurrences", "Critical", "High", "Medium", "Low", "Info", "New error groups"], rows,
                  [("Occurrences", f"{sum(r[1] for r in rows):,}"), ("New error groups", f"{sum(fresh.values()):,}")])


@report("top-errors", "Top errors by impact", "errors", "The error groups that hurt the most customers in the period.",
        "RPT-015", icon="target", filters=("period", "product"))
def top_errors(ctx):
    a, b = _bounds(ctx)
    groups = _errors(ctx)
    agg = (ErrorOccurrence.objects.filter(company=ctx.company, error_group__in=groups, created_at__range=(a, b))
           .values("error_group").annotate(n=Count("id"), users=Count("user_ref", distinct=True, filter=~Q(user_ref=""))))
    by = {r["error_group"]: r for r in agg}
    rows = []
    for g in groups.filter(pk__in=by):
        r = by[g.pk]
        rows.append([g.title, g.product.name, g.get_severity_display(), g.get_status_display(), r["n"], r["users"],
                     g.occurrence_count, g.last_seen, g.regression_count])
    rows.sort(key=lambda r: (-r[4] * (5 - SEVERITY[r[2].lower()]), r[0]))
    return Result(["Error", "Project", "Severity", "Status", "Occurrences in period", "Users affected in period",
                   "Occurrences all time", "Last seen", "Times it came back"], rows[:100],
                  [("Error groups hit", f"{len(rows):,}")], "Ranked by occurrences, weighted up for severity. Top 100.")


@report("error-queue", "Untriaged error queue", "errors", "Error groups still marked open, how long they have waited, and whether a ticket exists.",
        "RPT-022", icon="clock", filters=("product",))
def error_queue(ctx):
    now = timezone.now()
    groups = _errors(ctx).filter(status="open").annotate(tickets_n=Count("tickets"))
    rows = [[g.title, g.product.name, g.get_severity_display(), g.occurrence_count, g.first_seen, g.last_seen,
             (now - g.first_seen).days, "Yes" if g.tickets_n else "No"] for g in groups]
    rows.sort(key=lambda r: (SEVERITY[r[2].lower()], -r[6]))
    return Result(["Error", "Project", "Severity", "Occurrences", "First seen", "Last seen", "Days waiting", "Has a ticket"], rows,
                  [("Waiting", f"{len(rows):,}"), ("Critical or high", f"{sum(r[2] in ('Critical', 'High') for r in rows):,}"),
                   ("No ticket", f"{sum(r[7] == 'No' for r in rows):,}")])


@report("survey-scores", "Survey scores by month", "customers", "NPS, CSAT and CES per survey, month by month.",
        "RPT-024", icon="headset", filters=("period", "product"))
def survey_scores(ctx):
    a, b = _bounds(ctx)
    surveys = Survey.objects.filter(company=ctx.company, product__in=ctx.products)
    if ctx.product:
        surveys = surveys.filter(product=ctx.product)
    per = defaultdict(list)
    sv = {s.pk: s for s in surveys.select_related("product")}
    for r in SurveyResponse.objects.filter(company=ctx.company, survey__in=sv, created_at__range=(a, b)):
        per[(timezone.localtime(r.created_at).strftime("%Y-%m"), r.survey_id)].append(r.score)
    rows = []
    for (month, sid), scores in sorted(per.items()):
        s, n = sv[sid], len(scores)
        labels = [s.score_label(x) for x in scores]
        pos = sum(l in ("Promoter", "Satisfied", "Easy") for l in labels)
        neg = sum(l in ("Detractor", "Unsatisfied", "Difficult") for l in labels)
        rows.append([month, s.product.name, s.name, s.get_survey_type_display(), n, round(sum(scores) / n, 1),
                     round(pos * 100 / n), round(neg * 100 / n), round((pos - neg) * 100 / n) if s.survey_type == "nps" else None])
    return Result(["Month", "Project", "Survey", "Type", "Responses", "Average score", "Positive %", "Negative %", "NPS"], rows,
                  [("Responses", f"{sum(r[4] for r in rows):,}")],
                  "Positive means promoter (NPS), satisfied (CSAT) or easy (CES). NPS is positive minus negative, only for NPS surveys.")


@report("app-feedback", "In-app feedback ratings", "customers", "What users rate us through the SDK, by project and version.",
        "RPT-026", icon="messages-square", filters=("period", "product"))
def app_feedback(ctx):
    a, b = _bounds(ctx)
    qs = Feedback.objects.filter(company=ctx.company, product__in=ctx.products, created_at__range=(a, b)).select_related("product", "version")
    if ctx.product:
        qs = qs.filter(product=ctx.product)
    per = defaultdict(list)
    for f in qs:
        per[(f.product.name, f.version.version_string if f.version else "Unknown version")].append(f)
    rows = []
    for (p, v), fs in sorted(per.items()):
        n = len(fs)
        rows.append([p, v, n, round(sum(f.rating for f in fs) / n, 2), sum(f.rating <= 2 for f in fs),
                     round(sum(f.rating <= 2 for f in fs) * 100 / n), sum(bool(f.comment) for f in fs), max(f.created_at for f in fs)])
    return Result(["Project", "Version", "Ratings", "Average (out of 5)", "Low ratings (1-2)", "Low %", "With a comment", "Latest"], rows,
                  [("Ratings", f"{sum(r[2] for r in rows):,}")])


@report("lead-funnel", "Lead funnel by month", "customers", "How many leads each month reached contacted, qualified and converted.",
        "RPT-043", icon="target", admin=True, filters=("period",))
def lead_funnel(ctx):
    a, b = _bounds(ctx)
    leads = list(Lead.objects.filter(company=ctx.company, created_at__range=(a, b)))
    per = defaultdict(lambda: dict.fromkeys(("new", "contacted", "qualified", "converted", "lost"), 0))
    days = []
    for l in leads:
        per[timezone.localtime(l.created_at).strftime("%Y-%m")][l.status] += 1
        if l.converted_at:
            days.append((l.converted_at - l.created_at).days)
    rows = [[m, sum(v.values()), v["new"], v["contacted"], v["qualified"], v["converted"], v["lost"],
             round(v["converted"] * 100 / sum(v.values()), 1)] for m, v in sorted(per.items())]
    conv = sum(r[5] for r in rows)
    return Result(["Month received", "Leads", "Still new", "Contacted", "Qualified", "Converted", "Lost", "Converted %"], rows,
                  [("Leads", f"{len(leads):,}"), ("Converted", f"{conv:,}"),
                   ("Median days to convert", f"{int(statistics.median(days))}" if days else "—")],
                  "Counts show where each month's leads stand today.")


@report("lead-response", "Speed to first contact", "customers", "How long each website lead waited before anyone touched it.",
        "RPT-044", icon="clock", admin=True, filters=("period",))
def lead_response(ctx):
    a, b = _bounds(ctx)
    qs = Lead.objects.filter(company=ctx.company, created_at__range=(a, b)).annotate(first=Min("logs__created_at")).order_by("-created_at")
    rows, waits = [], []
    for l in qs:
        h = round((l.first - l.created_at).total_seconds() / 3600, 1) if l.first else None
        if h is not None:
            waits.append(h)
        rows.append([l.full_name, l.company_name, l.need, l.created_at, l.first, h, l.get_status_display()])
    never = sum(r[4] is None for r in rows)
    return Result(["Lead", "Company", "Needs", "Received", "First touched", "Hours to first contact", "Status"], rows,
                  [("Leads", f"{len(rows):,}"), ("Never touched", f"{never:,}"),
                   ("Median hours to contact", f"{statistics.median(waits):.1f}" if waits else "—")])


@report("project-portfolio", "Project portfolio", "projects", "Every project with its stage, dates, open work and last update.",
        "RPT-030", icon="package", filters=("product",))
def project_portfolio(ctx):
    prods = ctx.products.select_related("lead").order_by("name")
    if ctx.product:
        prods = prods.filter(pk=ctx.product.pk)
    ids = list(prods.values_list("pk", flat=True))
    open_t = dict(Ticket.objects.filter(product__in=ids).exclude(status__in=CLOSED).values_list("product").annotate(n=Count("id")))
    open_e = dict(ErrorGroup.objects.filter(product__in=ids, status__in=("open", "investigating")).values_list("product").annotate(n=Count("id")))
    crunch = dict(CrunchItem.objects.filter(product__in=ids, done=False).values_list("product").annotate(n=Count("id")))
    last = dict(ProjectLogEntry.objects.filter(product__in=ids).values_list("product").annotate(m=Max("created_at")))
    today, rows = ctx.today, []
    for p in prods:
        since = (today - timezone.localtime(p.stage_changed_at).date()).days if p.stage_changed_at else None
        past = (today - p.end_date).days if p.end_date and p.end_date < today and p.stage not in ("live", "close") else 0
        rows.append([p.name, p.key, STAGE_LABELS.get(p.stage, p.stage), _name(p.lead) if p.lead else "", since, p.start_date, p.end_date,
                     past, open_t.get(p.pk, 0), open_e.get(p.pk, 0), crunch.get(p.pk, 0), last.get(p.pk)])
    return Result(["Project", "Key", "Stage", "Lead", "Days in stage", "Start", "Planned end", "Days past planned end",
                   "Open tickets", "Open errors", "Open crunch items", "Last project update"], rows,
                  [("Projects", f"{len(rows):,}"), ("Past planned end", f"{sum(bool(r[7]) for r in rows):,}")])

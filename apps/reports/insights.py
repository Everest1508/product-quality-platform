"""Batch 2: ticket durations, error quality, releases and lead follow-up."""

import statistics
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlsplit

from django.db.models import Count, Max, Min
from django.utils import timezone

from apps.dashboards.models import ActivityLog
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback
from apps.leads.models import Lead
from apps.products.models import ProductVersion
from apps.tickets.models import Ticket, TicketComment

from .registry import Result, report
from .work import CLOSED, SEVERITY, _bounds, _errors, _name, _tickets

H = 3600


def _med(xs):
    return round(statistics.median(xs), 1) if xs else None


def _p90(xs):
    return round(sorted(xs)[min(len(xs) - 1, int(len(xs) * 0.9))], 1) if xs else None


def _events(ctx, event, **extra):
    return ActivityLog.objects.filter(company=ctx.company, event_type=event, **extra)


@report("ticket-resolution-time", "Ticket resolution time", "tickets", "How long tickets take from creation to resolved, by project and priority.",
        "RPT-004", icon="clock", filters=("period", "product"))
def ticket_resolution_time(ctx):
    a, b = _bounds(ctx)
    tq = _tickets(ctx)
    first = {}
    for tid, at in _events(ctx, "ticket_status_changed", created_at__range=(a, b), metadata__to__in=CLOSED,
                           target_object_id__in=tq.values("pk")).order_by("created_at").values_list("target_object_id", "created_at"):
        first.setdefault(tid, at)
    per = defaultdict(list)
    for t in tq.filter(pk__in=first):
        per[(t.product.name if t.product else "No project", t.get_priority_display())].append((first[t.pk] - t.created_at).total_seconds() / H)
    rows = [[p, pr, len(x), _med(x), _p90(x), round(sum(h <= 72 for h in x) * 100 / len(x))] for (p, pr), x in sorted(per.items())]
    allh = [h for x in per.values() for h in x]
    return Result(["Project", "Priority", "Resolved", "Median hours", "Slowest 10% took (hours)", "Resolved within 3 days %"], rows,
                  [("Resolved", f"{len(allh):,}"), ("Median hours", f"{_med(allh)}" if allh else "—")],
                  "Resolved time comes from status changes in the activity log; tickets changed some other way are missing.")


@report("ticket-reopened", "Reopened tickets", "tickets", "Tickets that were resolved or closed and then moved back.",
        "RPT-008", icon="triangle-alert", filters=("period", "product"))
def ticket_reopened(ctx):
    a, b = _bounds(ctx)
    ids = {t.pk: t for t in _tickets(ctx)}
    rows = []
    for e in _events(ctx, "ticket_status_changed", created_at__range=(a, b), target_object_id__in=list(ids)).select_related("actor").order_by("-created_at"):
        m = e.metadata or {}
        if m.get("from") in CLOSED and m.get("to") not in CLOSED:
            t = ids[e.target_object_id]
            rows.append([t.key, t.title, t.product.name if t.product else "No project", e.created_at, _name(e.actor) if e.actor else "Unknown",
                         m.get("from"), m.get("to")])
    resolved = _events(ctx, "ticket_status_changed", created_at__range=(a, b), metadata__to__in=CLOSED, target_object_id__in=list(ids)).count()
    return Result(["Ticket", "Title", "Project", "Reopened on", "Reopened by", "Was", "Now"], rows,
                  [("Reopened", f"{len(rows):,}"), ("Reopen rate", f"{round(len(rows) * 100 / resolved)}%" if resolved else "—")])


@report("ticket-first-reply", "First reply on new tickets", "tickets", "How quickly someone other than the author first comments on a new ticket.",
        "RPT-010", icon="messages-square", filters=("period", "product"))
def ticket_first_reply(ctx):
    a, b = _bounds(ctx)
    ts = list(_tickets(ctx).filter(created_at__range=(a, b)).order_by("-created_at"))
    first = {}
    for c in TicketComment.objects.filter(ticket__in=ts).select_related("author").order_by("created_at"):
        if c.author_id and c.author_id != c.ticket.created_by_id:
            first.setdefault(c.ticket_id, c)
    rows, hours = [], []
    for t in ts:
        c = first.get(t.pk)
        h = round((c.created_at - t.created_at).total_seconds() / H, 1) if c else None
        if h is not None:
            hours.append(h)
        rows.append([t.key, t.title, t.product.name if t.product else "No project", t.created_at, c.created_at if c else None, h, _name(c.author) if c else "No reply yet"])
    return Result(["Ticket", "Title", "Project", "Created", "First reply", "Hours to first reply", "Replied by"], rows,
                  [("New tickets", f"{len(ts):,}"), ("No reply yet", f"{len(ts) - len(hours):,}"), ("Median hours", f"{_med(hours)}" if hours else "—")])


@report("errors-without-ticket", "Errors nobody is working on", "errors", "Open or investigating error groups that have no ticket.",
        "RPT-013", icon="eye-off", filters=("product",))
def errors_without_ticket(ctx):
    now = timezone.now()
    gs = _errors(ctx).filter(status__in=("open", "investigating")).annotate(n=Count("tickets")).filter(n=0)
    rows = [[g.title, g.product.name, g.get_severity_display(), g.get_status_display(), g.occurrence_count, g.affected_user_count, g.first_seen, (now - g.first_seen).days] for g in gs]
    rows.sort(key=lambda r: (SEVERITY[r[2].lower()], -r[4]))
    return Result(["Error", "Project", "Severity", "Status", "Occurrences", "Users affected", "First seen", "Days since first seen"], rows,
                  [("Without a ticket", f"{len(rows):,}"), ("Critical or high", f"{sum(r[2] in ('Critical', 'High') for r in rows):,}")])


@report("release-quality", "Release quality", "errors", "What each release brought: new errors, error volume, feedback and tickets in the first week.",
        "RPT-016", icon="package", filters=("product",))
def release_quality(ctx):
    vs = list(ProductVersion.objects.filter(company=ctx.company, product__in=ctx.products).select_related("product").order_by("product__name", "-released_at", "-created_at"))
    if ctx.product:
        vs = [v for v in vs if v.product_id == ctx.product.pk]
    new = dict(ErrorGroup.objects.filter(first_version__in=vs).values_list("first_version").annotate(n=Count("id")))
    occ = {r["version"]: r for r in ErrorOccurrence.objects.filter(version__in=vs).values("version").annotate(n=Count("id"), g=Count("error_group", distinct=True))}
    fb = defaultdict(list)
    for v, r in Feedback.objects.filter(version__in=vs).values_list("version", "rating"):
        fb[v].append(r)
    rows = []
    for v in vs:
        o = occ.get(v.pk, {})
        week = Ticket.objects.filter(product=v.product, created_at__gte=v.released_at, created_at__lt=v.released_at + timedelta(days=7)).count() if v.released_at else None
        r = fb.get(v.pk, [])
        rows.append([v.product.name, v.version_string, "Yes" if v.is_current else "", v.released_at, new.get(v.pk, 0), o.get("n", 0), o.get("g", 0),
                     len(r), round(sum(r) / len(r), 2) if r else None, week])
    return Result(["Project", "Version", "Current", "Released", "New error groups", "Occurrences", "Error groups seen", "Ratings", "Average rating", "Tickets in first 7 days"], rows,
                  [("Versions", f"{len(rows):,}")], "Needs the SDK to send the app version with errors and feedback.")


@report("error-regressions", "Errors that came back", "errors", "Fixed errors that were reported again, how often, and from which release.",
        "RPT-017", icon="history", filters=("period", "product"))
def error_regressions(ctx):
    a, b = _bounds(ctx)
    gs = _errors(ctx).filter(regression_count__gt=0, regressed_at__range=(a, b)).select_related("first_version").order_by("-regressed_at")
    rows = [[g.title, g.product.name, g.get_severity_display(), g.get_status_display(), g.regression_count, g.regressed_at,
             g.first_version.version_string if g.first_version else "", g.occurrence_count] for g in gs]
    return Result(["Error", "Project", "Severity", "Status", "Times it came back", "Last came back", "First seen in version", "Occurrences"], rows,
                  [("Errors that came back", f"{len(rows):,}"), ("More than once", f"{sum(r[4] > 1 for r in rows):,}")])


@report("error-response-time", "Error triage and fix time", "errors", "How long from first sighting to someone acting, and to resolved, by severity.",
        "RPT-018", icon="clock", filters=("period", "product"))
def error_response_time(ctx):
    a, b = _bounds(ctx)
    gs = {g.pk: g for g in _errors(ctx)}
    touch, done = {}, {}
    evs = ActivityLog.objects.filter(company=ctx.company, event_type__in=("error_status_changed", "error_resolved", "error_ignored"),
                                     target_object_id__in=list(gs)).order_by("created_at")
    for e in evs:
        touch.setdefault(e.target_object_id, e.created_at)
        if e.event_type == "error_resolved" or (e.metadata or {}).get("to") == "resolved":
            done.setdefault(e.target_object_id, e.created_at)
    per = defaultdict(lambda: {"t": [], "r": []})
    for gid, at in done.items():
        if a <= at <= b:
            g = gs[gid]
            per[g.get_severity_display()]["r"].append((at - g.first_seen).total_seconds() / H)
            per[g.get_severity_display()]["t"].append((touch[gid] - g.first_seen).total_seconds() / H)
    rows = [[s, len(d["r"]), _med(d["t"]), _med(d["r"]), _p90(d["r"]), round(sum(h <= 24 for h in d["r"]) * 100 / len(d["r"]))]
            for s, d in sorted(per.items(), key=lambda x: SEVERITY[x[0].lower()])]
    return Result(["Severity", "Resolved", "Median hours to first action", "Median hours to resolved", "Slowest 10% took (hours)", "Resolved within a day %"], rows,
                  [("Resolved", f"{sum(r[1] for r in rows):,}")], "Resolved in the period; times come from the activity log.")


@report("lead-stale", "Leads waiting too long", "customers", "Open leads and how long since anyone touched them.",
        "RPT-045", icon="clock", admin=True, filters=())
def lead_stale(ctx):
    now = timezone.now()
    rows = []
    for l in Lead.objects.filter(company=ctx.company, is_submission=False).exclude(status__in=("converted", "lost")).annotate(last=Max("logs__created_at")):
        t = l.last or l.created_at
        rows.append([l.full_name, l.company_name, l.need, l.get_status_display(), l.created_at, l.last, (now - t).days])
    rows.sort(key=lambda r: -r[6])
    return Result(["Lead", "Company", "Needs", "Status", "Received", "Last activity", "Days idle"], rows,
                  [("Open leads", f"{len(rows):,}"), ("Idle 7+ days", f"{sum(r[6] >= 7 for r in rows):,}")])


@report("lead-demand", "What leads ask for", "customers", "Leads by what they need, how many convert, and how fast.",
        "RPT-046", icon="target", admin=True, filters=("period",))
def lead_demand(ctx):
    a, b = _bounds(ctx)
    per = defaultdict(lambda: {"n": 0, "c": 0, "d": []})
    for l in Lead.objects.filter(company=ctx.company, is_submission=False, created_at__range=(a, b)):
        d = per[l.need or "Not said"]
        d["n"] += 1
        if l.status == "converted":
            d["c"] += 1
            if l.converted_at:
                d["d"].append((l.converted_at - l.created_at).days)
    rows = sorted(([k, d["n"], d["c"], round(d["c"] * 100 / d["n"], 1), int(statistics.median(d["d"])) if d["d"] else None] for k, d in per.items()), key=lambda r: -r[1])
    return Result(["Need", "Leads", "Converted", "Converted %", "Median days to convert"], rows, [("Leads", f"{sum(r[1] for r in rows):,}")])

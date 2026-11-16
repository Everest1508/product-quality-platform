"""Audit log and access changes. Owner/admin only."""

from apps.dashboards.models import ActivityLog

from .registry import Result, report
from .work import _bounds, _name

ACCESS = ["member_joined", "member_removed", "member_role_changed", "access_granted", "access_revoked", "api_key_created", "api_key_revoked"]
EXPORT_CAP = 20000


def _rows(qs):
    return [[e.created_at, _name(e.actor) if e.actor else "System", e.get_event_type_display(), e.title, e.description] for e in qs]


@report("audit-log", "Audit log", "audit", "Everything done in the workspace, who did it and when, as a file for an auditor.",
        "RPT-086", icon="history", admin=True, filters=("period", "person"))
def audit_log(ctx):
    a, b = _bounds(ctx)
    qs = ActivityLog.objects.filter(company=ctx.company, created_at__range=(a, b)).select_related("actor").order_by("-created_at")
    if ctx.person:
        qs = qs.filter(actor=ctx.person)
    n = qs.count()
    return Result(["When", "Who", "Event", "What", "Details"], _rows(qs[:EXPORT_CAP]), [("Events", f"{n:,}")],
                  f"Limited to the newest {EXPORT_CAP:,} events." if n > EXPORT_CAP else "")


@report("access-changes", "Access and role changes", "audit", "Who joined, left, changed role, or got product access or API keys.",
        "RPT-087", icon="users", admin=True, filters=("period", "person"))
def access_changes(ctx):
    a, b = _bounds(ctx)
    qs = ActivityLog.objects.filter(company=ctx.company, event_type__in=ACCESS, created_at__range=(a, b)).select_related("actor").order_by("-created_at")
    if ctx.person:
        qs = qs.filter(actor=ctx.person)
    rows = _rows(qs)
    return Result(["When", "Who did it", "Event", "What", "Details"], rows, [("Changes", f"{len(rows):,}")])

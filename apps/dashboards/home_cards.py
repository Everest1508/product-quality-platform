"""Data for the Home cards that owners and admins (and, for errors, everyone) see.

Kept apart from `service.py`, which is already long. Each function returns plain data a
template can print; none of them writes anything.
"""
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.errors import trends
from apps.ingestion.models import ErrorOccurrence
from apps.products.access import accessible_error_groups

_STATE_ORDER = {"in": 0, "late": 0, "out": 1, "not_in": 2, "leave": 3, "off": 4}


def approvals(user, company):
    """Pending leave requests and attendance corrections, oldest first, with a count."""
    from apps.attendance import corrections
    from apps.attendance.models import AttendanceCorrection
    from apps.leave.models import LeaveRequest

    leave_qs = LeaveRequest.objects.filter(company=company, status="pending")
    corr_qs = AttendanceCorrection.objects.filter(company=company, status="pending")
    items = []
    for lv in leave_qs.select_related("user", "policy").order_by("start_date")[:5]:
        items.append({"kind": "leave", "obj": lv, "who": lv.user, "sort": lv.start_date, "can": True})
    for c in corr_qs.select_related("user").order_by("date")[:5]:
        items.append({"kind": "correction", "obj": c, "who": c.user, "sort": c.date, "can": corrections.can_decide(user, c)})
    items.sort(key=lambda i: i["sort"])
    return {"items": items[:6], "count": leave_qs.count() + corr_qs.count()}


def team_board(company, today):
    """Everyone in the company with where they are today: working, done, on leave or not in yet."""
    from apps.attendance import service as att

    shift = att.shift_for(company)
    weekly_off = shift.is_weekly_off(today)
    rows, counts = [], {"in": 0, "out": 0, "leave": 0, "not_in": 0, "late": 0}
    for r in att.get_team_today(company, today):
        rec = r["record"]
        has_in = bool(rec and rec.check_in)
        if r["on_leave"]:
            state = "leave"
        elif has_in and not rec.check_out:
            state = "in"
        elif has_in:
            state = "out"
        elif weekly_off:
            state = "off"
        else:
            state = "not_in"
        late = att.lateness_for(rec, shift) if has_in else 0
        if state in counts:
            counts[state] += 1
        if late:
            counts["late"] += 1
        rows.append({"user": r["user"], "record": rec, "state": state, "late": late})
    rows.sort(key=lambda x: (_STATE_ORDER[x["state"]], x["user"].username))
    return {"rows": rows, "counts": counts, "weekly_off": weekly_off}


def error_pulse(user, company, days=14):
    """Occurrences per day for the errors this person can open, this week against last."""
    groups = accessible_error_groups(user, company)
    day_list = trends._days(days)
    since = timezone.make_aware(datetime.combine(day_list[0], time.min))
    per_day = {
        row["day"]: row["n"]
        for row in ErrorOccurrence.objects.filter(error_group__in=groups, created_at__gte=since)
        .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id"))
    }
    counts = [per_day.get(d, 0) for d in day_list]
    week, before = sum(counts[-7:]), sum(counts[:7])
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    new_week = groups.filter(first_seen__gte=week_ago).count()
    new_before = groups.filter(first_seen__gte=now - timedelta(days=14), first_seen__lt=week_ago).count()
    noisiest = list(
        groups.exclude(status__in=("resolved", "ignored"))
        .annotate(week=Count("occurrences", filter=Q(occurrences__created_at__gte=week_ago)))
        .filter(week__gt=0).select_related("product").order_by("-week")[:3]
    )
    return {
        "spark": trends.sparkline(counts),
        "week": week, "before": before, "delta": week - before,
        "new_week": new_week, "new_delta": new_week - new_before,
        "regressed": groups.filter(regression_count__gt=0).exclude(status__in=("resolved", "ignored")).count(),
        "noisiest": noisiest,
    }


FEED_EVENTS = (
    "ticket_created", "ticket_resolved", "ticket_assigned", "ticket_status_changed",
    "error_created", "error_resolved", "product_created", "member_joined",
)


def activity_feed(company, limit=8):
    """The latest things worth a glance, newest first, each with a link when it points at a live ticket or error."""
    from django.urls import reverse

    from apps.dashboards.models import ActivityLog

    rows = list(
        ActivityLog.objects.filter(company=company, event_type__in=FEED_EVENTS)
        .select_related("actor").order_by("-created_at")[:limit]
    )
    names = {"ticket": "tickets:ticket_detail", "error": "errors:error_detail"}
    for r in rows:
        r.link = reverse(names[r.target_content_type], args=[r.target_object_id]) if r.target_content_type in names and r.target_object_id else ""
    return rows

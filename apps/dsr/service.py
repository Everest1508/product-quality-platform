from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.dsr.models import DSREntry


def submission_window(day, is_privileged=False):
    """Whether a DSR day still accepts writes, and why not when it doesn't.

    A DSR day is submitted on the day itself, so it closes when the local
    calendar rolls over: at 23:59 local `today == day` and the sheet is still
    open, and at 00:00 the same sheet becomes a past day. That is the
    "submit by 11:59pm" boundary -- it is derived from the local date rather
    than a stored cutoff, so it cannot drift out of step with the timezone.

    Past days stay readable but read-only, so an earlier sheet can be checked
    and not rewritten. Owners and admins are the override for a forgotten or
    mistyped entry. Future days are closed to *everyone*: hours cannot be
    worked yet, and there is no business reason for an admin to pre-log them,
    so granting an override there would only let bad data in.

    Returns ``(can_submit, reason)``; ``reason`` is user-facing copy.
    """
    today = timezone.localdate()
    if day > today:
        return False, "That day has not happened yet. You can only log work up to today."
    if day < today and not is_privileged:
        return False, "This day is closed. It stays readable, but only today can be edited."
    return True, ""


def auto_log_ticket_dsr(ticket, actor=None):
    """Automatically log or update a DSR entry when a ticket is completed/resolved."""
    if ticket.status not in ["resolved", "closed"]:
        return

    now = timezone.now()
    log_date = timezone.localdate(now)

    start_time = ticket.created_at
    duration = now - start_time
    total_seconds = max(0, duration.total_seconds())
    hours_spent = Decimal(str(round(max(0.25, total_seconds / 3600), 2)))

    target_users = list(ticket.assignees.all())
    if not target_users:
        if actor:
            target_users = [actor]
        elif ticket.created_by:
            target_users = [ticket.created_by]

    category = DSREntry.Category.BUG_FIX if ticket.ticket_type == "bug" else DSREntry.Category.TICKET

    task_name = f"#{ticket.pk}: {ticket.title}"
    if ticket.product:
        task_name = f"[{ticket.product.name}] {task_name}"

    for user in target_users:
        DSREntry.objects.update_or_create(
            company=ticket.company,
            user=user,
            ticket=ticket,
            date=log_date,
            defaults={
                "task_name": task_name,
                "category": category,
                "created_time": start_time,
                "completed_time": now,
                "hours_spent": hours_spent,
                "status": DSREntry.Status.COMPLETED,
                "is_auto_logged": True,
            },
        )


# --- Suggestions from the day's work ----------------------------------------

_TOUCH_EVENTS = ("ticket_created", "ticket_status_changed", "ticket_commented", "ticket_assigned")


def _quarter_hours(start, end):
    """The span between two moments as hours in quarters, kept within 0.5 to 4.

    A guess to prefill the box, never a record. Someone who touched a ticket at
    9:05 and again at 9:40 probably did not work eight hours on it, and one who
    touched it once has nothing to measure, so that case gets a flat hour.
    """
    minutes = (end - start).total_seconds() / 60
    if minutes < 15:
        return Decimal("1.00")
    quarters = round(minutes / 15)
    return Decimal(str(min(Decimal("4"), max(Decimal("0.5"), Decimal(quarters) / 4)))).quantize(Decimal("0.01"))


def suggestions(company, user, day, limit=8):
    """Tickets this person worked on that day that are not in their DSR yet.

    Built from what they did (the activity log) plus tickets assigned to them and
    still in progress. Scoped with `accessible_tickets`, so a suggestion can never
    name a ticket from a product they cannot open. Tickets already logged for the
    day, by hand or automatically, are left out.
    """
    from datetime import datetime, time

    from apps.dashboards.models import ActivityLog
    from apps.products.access import accessible_tickets

    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    logs = ActivityLog.objects.filter(
        company=company,
        actor=user,
        created_at__gte=start,
        created_at__lt=end,
        target_content_type="ticket",
        event_type__in=_TOUCH_EVENTS,
    ).order_by("created_at")
    touched = {}
    for log in logs:
        if log.target_object_id:
            touched.setdefault(log.target_object_id, []).append(log)

    visible = accessible_tickets(user, company)
    in_progress = set(
        visible.filter(assignees=user, status__in=["in_progress", "testing"]).values_list("pk", flat=True)
    )
    logged = set(
        DSREntry.objects.filter(company=company, user=user, date=day, ticket__isnull=False).values_list(
            "ticket_id", flat=True
        )
    )
    ids = (set(touched) | in_progress) - logged
    tickets = {t.pk: t for t in visible.filter(pk__in=ids).select_related("product")}

    rows = []
    for pk, ticket in tickets.items():
        events = touched.get(pk, [])
        did = []
        status_changes = [e for e in events if e.event_type == "ticket_status_changed"]
        if status_changes:
            to = (status_changes[-1].metadata or {}).get("to") or ticket.status
            did.append("resolved it" if to in ("resolved", "closed") else f"moved it to {to.replace('_', ' ')}")
        if any(e.event_type == "ticket_commented" for e in events):
            did.append("commented")
        if any(e.event_type == "ticket_created" for e in events):
            did.append("created it")
        if any(e.event_type == "ticket_assigned" for e in events):
            did.append("changed who it is assigned to")
        if not did:
            did.append("assigned to you, in progress")
        rows.append(
            {
                "ticket": ticket,
                "number": ticket.pk,
                "title": ticket.title,
                "product": ticket.product.name if ticket.product else "",
                "did": ", ".join(did).capitalize() if len(did) == 1 else ", ".join(did[:-1]).capitalize() + " and " + did[-1],
                "touched": bool(events),
                "hours": _quarter_hours(events[0].created_at, events[-1].created_at) if len(events) > 1 else Decimal("1.00"),
                "category": (
                    DSREntry.Category.BUG_FIX if ticket.ticket_type == "bug"
                    else DSREntry.Category.FEATURE if ticket.ticket_type == "feature"
                    else DSREntry.Category.TICKET
                ),
                "status": (
                    DSREntry.Status.COMPLETED if ticket.status in ("resolved", "closed") else DSREntry.Status.IN_PROGRESS
                ),
                "last": events[-1].created_at if events else None,
            }
        )
    rows.sort(key=lambda r: (not r["touched"], -(r["last"].timestamp() if r["last"] else 0), r["number"]))
    return rows[:limit]

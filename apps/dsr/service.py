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

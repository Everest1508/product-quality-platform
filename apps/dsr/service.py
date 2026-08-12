from decimal import Decimal
from django.utils import timezone
from apps.dsr.models import DSREntry


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

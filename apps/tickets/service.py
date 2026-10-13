"""Ticket actions with their side effects (activity log, notifications, webhook).

Shared by the HTML views and the JSON API so a status move or a delete does the
same things whichever door it comes through.
"""

from apps.dashboards.service import log_activity
from apps.notifications import service as notifications
from apps.notifications.models import Notification
from apps.products.webhook import notify_ticket_status_changed


def can_delete_ticket(user, company_role, ticket):
    """Owners and admins can delete any ticket; everyone else only their own."""
    return company_role in ("owner", "admin") or ticket.created_by_id == user.pk


def change_status(ticket, new_status, actor, company):
    """Move a ticket. Returns None on success, or an error message and no change."""
    if not ticket.can_transition_to(new_status):
        return f"'{new_status}' is not a valid status."
    old_value = ticket.status
    old_display = ticket.get_status_display()
    ticket.transition_to(new_status, actor=actor)
    notify_ticket_status_changed(ticket, old_display)
    notifications.notify_many(
        ticket.watchers.all(),
        company=company,
        kind=Notification.Kind.COMMENT,
        title=f"{ticket.key} moved to {ticket.get_status_display()}",
        body=ticket.title,
        url=f"/tickets/{ticket.pk}/",
        actor=actor,
    )
    log_activity(
        company, "ticket_status_changed",
        f"Ticket {ticket.key} status changed",
        description=f"{old_display} → {ticket.get_status_display()}",
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id, "from": old_value, "to": ticket.status},
    )
    return None


def delete_ticket(ticket, actor, company):
    """Delete a ticket and log it. Returns the ticket's key for the caller's message."""
    ticket_id, key, product_id, title = ticket.pk, ticket.key, ticket.product_id, ticket.title
    ticket.delete()
    log_activity(
        company, "ticket_deleted",
        f"Ticket {key} deleted",
        description=title,
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket_id,
        metadata={"product_id": product_id},
    )
    return key

"""Ticket actions with their side effects (activity log, notifications, webhook).

Shared by the HTML views and the JSON API so a status move or a delete does the
same things whichever door it comes through.
"""

from django.contrib.auth import get_user_model

from apps.core.timefmt import t12
from apps.dashboards.service import log_activity
from apps.notifications import service as notifications
from apps.notifications.models import Notification
from apps.products.webhook import notify_ticket_assigned, notify_ticket_created, notify_ticket_status_changed
from apps.tickets import mentions
from apps.tickets.forms import TicketCreateForm, TicketEditForm
from apps.tickets.models import Ticket, TicketComment


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


# --- the rest of the ticket actions: each does what its classic view did, side effects included ---



def set_priority(ticket, new_priority, actor, company):
    """Returns None on success, or an error message and no change."""
    if new_priority not in dict(Ticket.Priority.choices):
        return f"'{new_priority}' is not a valid priority."
    old = ticket.get_priority_display()
    ticket.priority = new_priority
    ticket.save(update_fields=["priority", "updated_at"])
    log_activity(
        company, "ticket_priority_changed",
        f"Ticket {ticket.key} priority changed to {ticket.get_priority_display()}",
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id, "from": old, "to": ticket.get_priority_display()},
    )
    return None


def assign(ticket, user_ids, actor, company):
    """Replace the assignees with the company members among `user_ids`.

    Moves open to assigned when the first person is added, and back to open when
    the last is removed. Returns the message the classic page showed."""
    User = get_user_model()
    old_assignees = set(ticket.assignees.values_list("pk", flat=True))
    old_status = ticket.status
    if user_ids:
        people = User.objects.filter(pk__in=user_ids, memberships__company=company).distinct()
        ticket.set_assignees(people, actor=actor)
        if ticket.status == "open":
            ticket.status = "assigned"
            ticket.save(update_fields=["status", "updated_at"])
    else:
        ticket.set_assignees([])
        if ticket.status == "assigned":
            ticket.status = "open"
            ticket.save(update_fields=["status", "updated_at"])

    new_assignees = set(ticket.assignees.values_list("pk", flat=True))
    names = ", ".join(a.get_full_name() or a.username for a in ticket.assignees.order_by("username")) or "nobody"
    notify_ticket_assigned(ticket)
    log_activity(
        company, "ticket_assigned",
        f"Ticket {ticket.key} assigned",
        description=f"Assigned to {names}",
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={
            "product_id": ticket.product_id,
            "assigned_to": ",".join(map(str, sorted(new_assignees))),
            "from": ",".join(map(str, sorted(old_assignees))),
            "to": ",".join(map(str, sorted(new_assignees))),
        },
    )
    moved = f" Status is now {ticket.get_status_display()}." if ticket.status != old_status else ""
    return f"{ticket.key} is now unassigned.{moved}" if names == "nobody" else f"{ticket.key} assigned to {names}.{moved}"


def set_deadline(ticket, deadline, actor, company):
    """`deadline` is an aware datetime, or None to clear it."""
    old = ticket.deadline
    ticket.deadline = deadline
    ticket.save(update_fields=["deadline", "updated_at"])
    log_activity(
        company, "ticket_deadline_changed",
        f"Ticket {ticket.key} deadline changed",
        description=(
            f"from {old:%Y-%m-%d} {t12(old)} to {deadline:%Y-%m-%d} {t12(deadline)}"
            if old and deadline
            else f"{deadline:%Y-%m-%d} {t12(deadline)}" if deadline else "Deadline cleared"
        ),
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={
            "product_id": ticket.product_id,
            "from": old.isoformat() if old else None,
            "to": deadline.isoformat() if deadline else None,
        },
    )


def toggle_follow(ticket, user, company):
    """Follow or unfollow. Returns True when the user now follows the ticket."""
    if ticket.watchers.filter(pk=user.pk).exists():
        ticket.watchers.remove(user)
        event, title, following = "ticket_unfollowed", f"{user.username} unfollowed {ticket.key}", False
    else:
        ticket.watchers.add(user)
        event, title, following = "ticket_followed", f"{user.username} is following {ticket.key}", True
    log_activity(
        company, event, title,
        description=ticket.title[:200],
        actor=user,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id},
    )
    return following


def _notify_comment(ticket, body, mentioned, actor, company):
    """Mentioned people get a mention; the assignees, the creator and followers get a
    plain comment notice. Nobody gets both, and the author gets neither."""
    who = actor.get_full_name() or actor.username
    snippet = body.strip().replace("\n", " ")[:140]
    url = f"/tickets/{ticket.pk}/"
    notifications.notify_many(
        mentioned, company=company, kind=Notification.Kind.MENTION,
        title=f"{who} mentioned you on ticket {ticket.key}", body=snippet, url=url, actor=actor,
    )
    already = {u.pk for u in mentioned}
    watchers = [u for u in ticket.assignees.all() if u.pk not in already]
    if ticket.created_by and ticket.created_by.pk not in already:
        watchers.append(ticket.created_by)
    seen = already | {u.pk for u in watchers}
    watchers += [u for u in ticket.watchers.all() if u.pk not in seen]
    notifications.notify_many(
        watchers, company=company, kind=Notification.Kind.COMMENT,
        title=f"{who} commented on ticket {ticket.key}", body=snippet, url=url, actor=actor,
    )


def add_comment(ticket, body, actor, company):
    comment = TicketComment.objects.create(ticket=ticket, company=company, author=actor, body=body)
    mentioned = mentions.resolve(body, ticket, company)
    comment.mentions.set(mentioned)
    _notify_comment(ticket, body, mentioned, actor, company)
    log_activity(
        company, "ticket_commented",
        f"Comment on ticket {ticket.key}",
        description=body[:200],
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id},
    )
    return comment


def create_ticket(data, user, company, product=None):
    """Returns (ticket, form, warnings); ticket is None when the form is invalid.

    People without access to the chosen product are skipped, with a warning,
    rather than failing the whole form."""
    form = TicketCreateForm(data, company=company, user=user, product=product)
    if not form.is_valid():
        return None, form, []
    ticket = form.save(commit=False)
    ticket.company = company
    ticket.created_by = user
    ticket.source = "manual"
    if product:
        ticket.product = product
    ticket.save()
    assignees = list(form.cleaned_data["assignees"])
    warnings = []
    if ticket.product_id:
        from apps.products.access import product_users

        allowed = set(product_users(ticket.product, company).values_list("pk", flat=True))
        skipped = [u for u in assignees if u.pk not in allowed]
        assignees = [u for u in assignees if u.pk in allowed]
        if skipped:
            names = ", ".join(u.get_full_name() or u.username for u in skipped)
            warnings.append(f"Not assigned (no access to {ticket.product.name}): {names}.")
    ticket.set_assignees(assignees, actor=user)
    notify_ticket_created(ticket)
    log_activity(
        company, "ticket_created",
        f"Ticket {ticket.key} created",
        description=ticket.title,
        actor=user,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id},
    )
    return ticket, form, warnings


def update_ticket(data, ticket, actor, company):
    """Returns (ticket, form); ticket is None when the form is invalid."""
    form = TicketEditForm(data, instance=ticket)
    if not form.is_valid():
        return None, form
    ticket = form.save()
    ticket.set_assignees(form.cleaned_data["assignees"], actor=actor)
    log_activity(
        company, "ticket_updated",
        f"Ticket {ticket.key} updated",
        description=ticket.title,
        actor=actor,
        target_content_type="ticket",
        target_object_id=ticket.pk,
        metadata={"product_id": ticket.product_id},
    )
    return ticket, form

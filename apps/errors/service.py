"""Error group actions with their side effects, shared by the JSON API and the
two legacy dashboard buttons (resolve, ignore)."""

from apps.dashboards.service import log_activity
from apps.ingestion.models import ErrorGroup
from apps.tickets.models import Ticket


def set_status(group, new_status, actor, company):
    """Move a group. Returns None on success, or an error message and no change.

    Resolving and ignoring keep their own activity events; every other move is
    an `error_status_changed` with from/to."""
    if new_status not in dict(ErrorGroup.STATUS_CHOICES):
        return f"'{new_status}' is not a valid status."
    old = group.status
    group.status = new_status
    group.save(update_fields=["status"])
    meta = {"product_id": group.product_id}
    if new_status == "resolved":
        log_activity(company, "error_resolved", f"Error #{group.pk} resolved", description=group.title,
                     actor=actor, target_content_type="error", target_object_id=group.pk, metadata=meta)
    elif new_status == "ignored":
        log_activity(company, "error_ignored", f"Error #{group.pk} ignored", description=group.title,
                     actor=actor, target_content_type="error", target_object_id=group.pk, metadata=meta)
    else:
        log_activity(company, "error_status_changed", f"Error #{group.pk} status changed",
                     description=f"{old} → {new_status}", actor=actor, target_content_type="error",
                     target_object_id=group.pk, metadata={**meta, "from": old, "to": new_status})
    return None


def convert_to_ticket(group, actor, company):
    ticket = Ticket.objects.create(
        company=company,
        title=f"Error: {group.title}",
        description=(
            f"Auto-created from error #{group.pk}.\n\n"
            f"Fingerprint: {group.fingerprint}\n"
            f"Severity: {group.severity}\n"
            f"Occurrences: {group.occurrence_count}\n"
            f"Affected users: {group.affected_user_count}"
        ),
        ticket_type="bug",
        priority="high" if group.severity in ("critical", "high") else "medium",
        source="manual",
        created_by=actor,
        product=group.product,
        linked_error_group=group,
    )
    log_activity(
        company, "ticket_created", f"Ticket {ticket.key} created from error #{group.pk}",
        description=ticket.title, actor=actor, target_content_type="ticket", target_object_id=ticket.pk,
        metadata={"product_id": group.product_id, "error_group_id": group.pk},
    )
    return ticket


def delete_error(group, actor, company):
    """Delete a group and log it. Returns its id for the caller's message."""
    error_id, title, product_id = group.pk, group.title, group.product_id
    group.delete()
    log_activity(company, "error_deleted", f"Error #{error_id} deleted", description=title, actor=actor,
                 target_content_type="error", target_object_id=error_id, metadata={"product_id": product_id})
    return error_id

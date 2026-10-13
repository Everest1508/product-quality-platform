"""Ticket list filtering and sorting, shared by every ticket list and board."""

from django.utils import timezone


SORT_MAP = {
    "created": "created_at",
    "-created": "-created_at",
    "updated": "updated_at",
    "-updated": "-updated_at",
    "priority": "priority",
    "-priority": "-priority",
    "status": "status",
    "-status": "-status",
    "title": "title",
    "-title": "-title",
}

# The filters shared by the ticket kanban and list views, so both boards
# expose the same controls. Kanban additionally groups by status (columns);
# the List view adds a `status` dropdown on top of this.
TICKET_FILTER_KEYS = ("q", "type", "priority", "product", "assigned", "overdue", "sort")


def apply_ticket_filters(request, qs):
    """Apply the shared ticket filter querystring to ``qs``.

    Returns ``(qs, ctx)`` where ``ctx`` holds the ``current_*`` values used to
    re-render the filter bar. Does not apply ``sort`` (see ``sort_tickets``).
    """
    ctx = {}

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(title__icontains=search)
    ctx["search"] = search

    ticket_type = request.GET.get("type")
    if ticket_type:
        qs = qs.filter(ticket_type=ticket_type)
    ctx["current_type"] = ticket_type

    priority = request.GET.get("priority")
    if priority:
        qs = qs.filter(priority=priority)
    ctx["current_priority"] = priority

    product_id = request.GET.get("product")
    if product_id:
        qs = qs.filter(product_id=product_id)
    ctx["current_product"] = product_id

    assigned = request.GET.get("assigned")
    if assigned == "me":
        qs = qs.filter(assignees=request.user)
    elif assigned == "unassigned":
        qs = qs.filter(assignees__isnull=True)
    elif assigned:
        qs = qs.filter(assignees__id=assigned).distinct()
    ctx["current_assigned"] = assigned

    overdue = request.GET.get("overdue")
    if overdue:
        qs = qs.filter(
            deadline__isnull=False,
            deadline__lt=timezone.now(),
        ).exclude(status__in=["resolved", "closed"])
    ctx["current_overdue"] = overdue

    ctx["current_sort"] = request.GET.get("sort", "")
    return qs, ctx


def sort_tickets(request, qs, default):
    """Order ``qs`` by the ``sort`` querystring, falling back to ``default``
    (a tuple of field names) when it is missing or unrecognised."""
    sort = request.GET.get("sort", "")
    if sort in SORT_MAP:
        return qs.order_by(SORT_MAP[sort])
    return qs.order_by(*default)


# Statuses that no longer count as work in progress. The sidebar badge, the
# dashboard and the list headers all use this one definition, so the numbers agree.
OPEN_EXCLUDED = ("resolved", "closed")

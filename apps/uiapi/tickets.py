from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.products.access import (
    accessible_products,
    accessible_tickets,
    product_users,
    require_product_access,
    require_ticket_access,
    user_has_product_access,
)
from apps.products.models import Product
from apps.tickets.filters import OPEN_EXCLUDED, apply_ticket_filters, sort_tickets
from apps.tickets.models import Ticket
from apps.tickets import service as ticket_service
from apps.tickets.service import can_delete_ticket
from apps.uiapi.views import CompanyAPIView

User = get_user_model()
PER_PAGE = 25
MAX_BULK = 500


def _name(user):
    return user.get_full_name() or user.username


def ticket_url(ticket):
    """The legacy detail page, mirroring tickets.views._ticket_redirect."""
    if ticket.product_id:
        return f"/products/{ticket.product_id}/tickets/{ticket.pk}/"
    return f"/tickets/{ticket.pk}/"


def ticket_json(ticket, user, role):
    return {
        "id": ticket.pk,
        "key": ticket.key,
        "title": ticket.title,
        "status": ticket.status,
        "status_label": ticket.get_status_display(),
        "priority": ticket.priority,
        "priority_label": ticket.get_priority_display(),
        "type": ticket.ticket_type,
        "type_label": ticket.get_ticket_type_display(),
        "product": {"id": ticket.product_id, "name": ticket.product.name} if ticket.product_id else None,
        "assignees": [
            {"id": a.pk, "name": _name(a), "initial": (a.username[:1] or "?").upper()} for a in ticket.assignees.all()
        ],
        "deadline": ticket.deadline.isoformat() if ticket.deadline else None,
        "is_overdue": ticket.is_overdue,
        "updated_at": ticket.updated_at.isoformat(),
        "linked_error": ticket.linked_error_group_id is not None,
        "can_delete": can_delete_ticket(user, role, ticket),
        "url": ticket_url(ticket),
    }


def scoped_product(request):
    """The product a product page is scoped to (`?scope=product&product=<pk>`), or None.

    Distinct from the plain `?product=` filter, which only narrows what the user
    can already see. 404 when the product is missing, in another company, or
    not one this user may open.
    """
    if request.query_params.get("scope") != "product":
        return None
    try:
        pk = int(request.query_params.get("product", ""))
    except ValueError:
        raise Http404
    product = get_object_or_404(Product, pk=pk, company=request.company)
    require_product_access(request._request, product)
    return product


class TicketListAPIView(CompanyAPIView):
    def get(self, request):
        product = scoped_product(request)
        qs = product.tickets.all() if product else accessible_tickets(request.user, request.company)
        qs = qs.select_related("product", "created_by").prefetch_related("assignees")
        qs, _ctx = apply_ticket_filters(request, qs)
        user, role = request.user, request.company_role

        if request.query_params.get("view") == "board":
            qs = sort_tickets(request, qs, default=("-priority", "-created_at"))
            columns = [
                {"key": v, "label": label, "tickets": [ticket_json(t, user, role) for t in qs.filter(status=v)]}
                for v, label in Ticket.Status.choices
            ]
            total = sum(len(c["tickets"]) for c in columns)
            open_count = sum(len(c["tickets"]) for c in columns if c["key"] not in OPEN_EXCLUDED)
            return Response({"view": "board", "columns": columns, "total": total, "open_count": open_count})

        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        qs = sort_tickets(request, qs, default=("-created_at",))
        page = Paginator(qs, PER_PAGE).get_page(request.query_params.get("page", 1))
        return Response({
            "view": "list",
            "items": [ticket_json(t, user, role) for t in page],
            "page": {
                "number": page.number,
                "num_pages": page.paginator.num_pages,
                "count": page.paginator.count,
                "per_page": PER_PAGE,
            },
            "open_count": qs.exclude(status__in=OPEN_EXCLUDED).count(),
        })


class TicketMetaAPIView(CompanyAPIView):
    """Choices for the filter bar."""

    def get(self, request):
        product = scoped_product(request)
        if product:
            members = product_users(product, request.company)
            products = []
        else:
            members = User.objects.filter(memberships__company=request.company).order_by("username")
            products = [
                {"id": p.pk, "name": p.name}
                for p in accessible_products(request.user, request.company).order_by("name")
            ]
        return Response({
            "statuses": [list(c) for c in Ticket.Status.choices],
            "types": [list(c) for c in Ticket.TicketType.choices],
            "priorities": [list(c) for c in Ticket.Priority.choices],
            "products": products,
            "members": [{"id": u.pk, "name": _name(u)} for u in members],
        })


def _ticket(request, pk):
    """A ticket in this company that the user may open, else 404."""
    ticket = get_object_or_404(Ticket.objects.select_related("product"), pk=pk, company=request.company)
    require_ticket_access(request._request, ticket)
    return ticket


class TicketStatusAPIView(CompanyAPIView):
    def post(self, request, pk):
        ticket = _ticket(request, pk)
        error = ticket_service.change_status(ticket, request.data.get("status"), request.user, request.company)
        if error:
            return Response({"detail": error}, status=400)
        return Response({"ok": True, "status": ticket.status})


class TicketDeleteAPIView(CompanyAPIView):
    def delete(self, request, pk):
        ticket = _ticket(request, pk)
        if not ticket_service.can_delete_ticket(request.user, request.company_role, ticket):
            raise PermissionDenied("You can only delete tickets you created.")
        return Response({"deleted": ticket_service.delete_ticket(ticket, request.user, request.company)})


class TicketBulkDeleteAPIView(CompanyAPIView):
    """Delete what the user may; skip (and count) the rest instead of failing the batch."""

    def post(self, request):
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "No tickets selected."}, status=400)
        ids = list(dict.fromkeys(str(i) for i in ids))[:MAX_BULK]  # each ticket once, bounded batch
        deleted = 0
        for raw in ids:
            try:
                ticket = Ticket.objects.select_related("product").get(pk=int(raw), company=request.company)
            except (Ticket.DoesNotExist, ValueError, TypeError):
                continue
            if ticket.product_id and not user_has_product_access(request.user, request.company, ticket.product):
                continue
            if not ticket_service.can_delete_ticket(request.user, request.company_role, ticket):
                continue
            ticket_service.delete_ticket(ticket, request.user, request.company)
            deleted += 1
        return Response({"deleted": deleted, "skipped": len(ids) - deleted})

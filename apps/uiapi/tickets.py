from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.dsr import service as dsr_service
from apps.dashboards.models import ActivityLog
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
from apps.tickets import mentions
from apps.tickets import service as ticket_service
from apps.tickets.forms import error_summary
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


def local_input(dt):
    """A deadline as the wall clock an <input type=datetime-local> wants, in the company timezone."""
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M") if dt else ""


def form_errors(form):
    """A 400 body: messages per field, and the one-line summary the classic page toasted."""
    return {
        "errors": {field: [e["message"] for e in errs] for field, errs in form.errors.get_json_data().items()},
        "detail": error_summary(form),
    }


def ticket_detail_json(ticket, user, role, company):
    """Everything the detail page shows and its controls need."""
    base = ticket_json(ticket, user, role)
    link = None
    if ticket.linked_error_group_id:
        eg = ticket.linked_error_group
        url = f"/products/{ticket.product_id}/errors/{eg.pk}/" if ticket.product_id else f"/errors/{eg.pk}/"
        link = {"id": eg.pk, "title": eg.title, "url": url}
    if ticket.product_id:
        members = product_users(ticket.product, company)
    else:
        members = User.objects.filter(memberships__company=company).order_by("username")
    return {
        "ticket": {
            **base,
            "description": ticket.description,
            "created_at": ticket.created_at.isoformat(),
            "source": ticket.source,
            "source_label": ticket.get_source_display(),
            "deadline_local": local_input(ticket.deadline),
            "linked_error": link,
            "created_by": {"id": ticket.created_by_id, "name": _name(ticket.created_by)} if ticket.created_by_id else None,
        },
        "comments": [
            {
                "id": c.pk,
                "author": {"id": c.author_id, "name": _name(c.author), "initial": (c.author.username[:1] or "?").upper()}
                if c.author_id else None,
                "created_at": c.created_at.isoformat(),
                "body": c.body,
                "mentions": [u.username for u in c.mentions.all()],
            }
            for c in ticket.comments.select_related("author").prefetch_related("mentions").all()
        ],
        "events": [
            {"id": a.pk, "title": a.title, "description": a.description, "actor": _name(a.actor) if a.actor_id else "", "created_at": a.created_at.isoformat()}
            for a in ActivityLog.objects.filter(company=company, target_content_type="ticket", target_object_id=ticket.pk)
            .exclude(event_type="ticket_commented").select_related("actor").order_by("created_at", "id")[:100]
        ],
        "following": ticket.watchers.filter(pk=user.pk).exists(),
        "watcher_count": ticket.watchers.count(),
        "members": [{"id": u.pk, "name": _name(u), "username": u.username} for u in members],
        "mention_candidates": mentions.candidates_json(ticket, company),
        "statuses": [list(c) for c in Ticket.Status.choices],
        "priorities": [list(c) for c in Ticket.Priority.choices],
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
    def post(self, request):
        """Create a ticket. The product, if any, comes from the body and must be one the user can open."""
        data = dict(request.data)
        data["product"] = data.get("product") or None
        ticket, form, warnings = ticket_service.create_ticket(data, request.user, request.company)
        if ticket is None:
            return Response(form_errors(form), status=400)
        ticket = Ticket.objects.select_related("product").prefetch_related("assignees").get(pk=ticket.pk)
        return Response(
            {
                "ticket": ticket_json(ticket, request.user, request.company_role),
                "key": ticket.key,
                "url": ticket_url(ticket),
                "warnings": warnings,
            },
            status=201,
        )

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
        body = {"ok": True, "status": ticket.status}
        waiting = dsr_service.pending_time_entry(request.company, request.user, ticket)
        if waiting is not None:  # a long-open ticket just logged to this person's DSR: tell them to add the time they worked
            body["dsr"] = {"needs_time": True, "key": ticket.key, "elapsed": dsr_service.elapsed_label(waiting)}
        return Response(body)


def detail_response(request, ticket, status=200, **extra):
    """The ticket as the detail page wants it, fresh from the database."""
    ticket = (
        Ticket.objects.select_related("product", "created_by", "linked_error_group")
        .prefetch_related("assignees")
        .get(pk=ticket.pk)
    )
    body = ticket_detail_json(ticket, request.user, request.company_role, request.company)
    return Response({**body, **extra}, status=status)


class TicketDetailAPIView(CompanyAPIView):
    def get(self, request, pk):
        return detail_response(request, _ticket(request, pk))

    def patch(self, request, pk):
        ticket = _ticket(request, pk)
        saved, form = ticket_service.update_ticket(request.data, ticket, request.user, request.company)
        if saved is None:
            return Response(form_errors(form), status=400)
        return detail_response(request, saved)

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


class _TicketActionView(CompanyAPIView):
    """Base for the small per-ticket actions: find the ticket (404 without access),
    do one thing through the service layer, answer with the ticket as the page shows it."""

    def post(self, request, pk):
        return self.act(request, _ticket(request, pk))


class TicketPriorityAPIView(_TicketActionView):
    def act(self, request, ticket):
        error = ticket_service.set_priority(ticket, request.data.get("priority"), request.user, request.company)
        if error:
            return Response({"detail": error}, status=400)
        return detail_response(request, ticket)


class TicketAssignAPIView(_TicketActionView):
    def act(self, request, ticket):
        raw = request.data.get("assignees") or []
        ids = [int(x) for x in raw if str(x).isdecimal()] if isinstance(raw, list) else []
        message = ticket_service.assign(ticket, ids, request.user, request.company)
        return detail_response(request, ticket, message=message)


class TicketDeadlineAPIView(_TicketActionView):
    def act(self, request, ticket):
        raw = request.data.get("deadline")
        if raw in (None, ""):
            deadline = None
        else:
            parsed = parse_datetime(str(raw))
            if parsed is None:
                return Response({"detail": "Enter a valid date and time."}, status=400)
            deadline = timezone.make_aware(parsed, timezone.get_current_timezone()) if timezone.is_naive(parsed) else parsed
        ticket_service.set_deadline(ticket, deadline, request.user, request.company)
        return detail_response(request, ticket)


class TicketFollowAPIView(_TicketActionView):
    def act(self, request, ticket):
        following = ticket_service.toggle_follow(ticket, request.user, request.company)
        message = (
            f"You are following {ticket.key}. You will be told about comments and status changes."
            if following else f"You unfollowed {ticket.key}."
        )
        return detail_response(request, ticket, message=message)


class TicketCommentAPIView(_TicketActionView):
    def act(self, request, ticket):
        body = str(request.data.get("body") or "").strip()
        if not body:
            return Response({"detail": "Comment cannot be empty."}, status=400)
        ticket_service.add_comment(ticket, body, request.user, request.company)
        return detail_response(request, ticket, status=201)

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.products.access import require_ticket_access
from apps.notifications import service
from apps.notifications.models import Notification
from apps.products.webhook import notify_ticket_assigned, notify_ticket_created
from apps.tickets.forms import error_summary, TicketCommentForm, TicketCreateForm, TicketDeadlineForm, TicketEditForm
from apps.tickets import mentions
from apps.uiapi.shell import render_shell
from apps.tickets import service as ticket_service
from apps.tickets.models import Ticket, TicketComment
from apps.core.timefmt import t12

User = get_user_model()


def _ticket_redirect(ticket):
    """Return (url_name, kwargs) pointing to the right detail page."""
    if ticket.product_id:
        return "products:product_ticket_detail", {"pk": ticket.product_id, "ticket_pk": ticket.pk}
    return "tickets:ticket_detail", {"pk": ticket.pk}


class TicketListView(CompanyMemberRequiredMixin, View):
    """The list, served by the React shell (data from /ui-api/v1/tickets/)."""

    def get(self, request):
        return render_shell(request)


class TicketKanbanView(CompanyMemberRequiredMixin, View):
    """The board, served by the React shell (data from /ui-api/v1/tickets/?view=board)."""

    def get(self, request):
        return render_shell(request)


class TicketCreateView(CompanyMemberRequiredMixin, View):
    """The new-ticket form, served by the React shell (saves through /ui-api/v1/tickets/)."""

    def get(self, request):
        return render_shell(request)


class TicketEditView(CompanyMemberRequiredMixin, View):
    """The edit form, served by the React shell (saves through PATCH /ui-api/v1/tickets/<pk>/)."""

    def get(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        return render_shell(request)


class TicketDetailView(CompanyMemberRequiredMixin, View):
    """The ticket page, served by the React shell (data from /ui-api/v1/tickets/<pk>/)."""

    def get(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        return render_shell(request)




class TicketStatusView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        new_status = request.POST.get("status")

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        old_display = ticket.get_status_display()
        error = ticket_service.change_status(ticket, new_status, request.user, request.company)
        if error:
            if is_ajax:
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
        else:
            if is_ajax:
                return JsonResponse({"ok": True, "status": ticket.status})
            messages.success(request, f"{ticket.key}: status {old_display} → {ticket.get_status_display()}.")

        if request.headers.get("HX-Request") == "true":
            members = User.objects.filter(
                memberships__company=request.company
            ).order_by("username")
            return render(request, "tickets/partials/_ticket_status.html", {
                "ticket": ticket,
                "status_choices": Ticket.Status.choices,
                "members": members,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketAssignView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        message = ticket_service.assign(ticket, request.POST.getlist("assignees"), request.user, request.company)
        messages.success(request, message)

        if request.headers.get("HX-Request") == "true":
            members = User.objects.filter(
                memberships__company=request.company
            ).order_by("username")
            if ticket.product:
                from apps.products.access import product_users
                members = product_users(ticket.product, request.company)
            return render(request, "tickets/partials/_ticket_assignee.html", {
                "ticket": ticket,
                "members": members,
                "assignee_selected_ids": [str(pk) for pk in ticket.assignees.values_list("pk", flat=True)],
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)











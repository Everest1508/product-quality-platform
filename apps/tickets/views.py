from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.products.access import require_ticket_access
from apps.tickets.models import Ticket
from apps.uiapi.shell import render_shell


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

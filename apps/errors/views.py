from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.errors import service
from apps.ingestion.models import ErrorGroup
from apps.products.access import require_error_group_access
from apps.uiapi.shell import render_shell


class ErrorShellView(CompanyMemberRequiredMixin, View):
    """The list and report pages, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class ErrorDetailView(CompanyMemberRequiredMixin, View):
    """The detail page, served by the React shell once the person may open it."""

    def get(self, request, pk):
        group = get_object_or_404(ErrorGroup.objects.select_related("product"), pk=pk, company=request.company)
        require_error_group_access(request, group)
        return render_shell(request)


class _DashboardButtonView(CompanyMemberRequiredMixin, View):
    """Resolve / ignore as the legacy home dashboard posts them (hx-post, no swap).
    Stays until the dashboard moves; the rules are in errors.service."""

    status = ""
    done = ""

    def post(self, request, pk):
        group = get_object_or_404(ErrorGroup, pk=pk, company=request.company)
        require_error_group_access(request, group)
        service.set_status(group, self.status, request.user, request.company)
        messages.success(request, self.done)
        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_error_status_badge.html", {"error_group": group})
        if group.product_id:
            return redirect("products:product_error_detail", pk=group.product_id, error_pk=group.pk)
        return redirect("errors:error_detail", pk=group.pk)


class ErrorIgnoreView(_DashboardButtonView):
    status, done = "ignored", "Error group ignored."


class ErrorResolveView(_DashboardButtonView):
    status, done = "resolved", "Error group resolved."

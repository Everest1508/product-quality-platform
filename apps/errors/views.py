from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
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

from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.feedback.models import Survey
from apps.products.access import accessible_products
from apps.uiapi.shell import render_shell


class SurveyShellView(CompanyMemberRequiredMixin, View):
    """The list, create form and CS hub, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class SurveyDetailView(CompanyMemberRequiredMixin, View):
    """404 unless the survey is in this company and on a product the person may open."""

    def get(self, request, pk):
        get_object_or_404(Survey, pk=pk, company=request.company, product__in=accessible_products(request.user, request.company))
        return render_shell(request)


class PublicSurveyView(View):
    """The public link. No login; the page itself is the React shell, which fetches an active survey or says it is not open."""

    def get(self, request, pk):
        get_object_or_404(Survey, pk=pk, status="active")
        return render_shell(request)

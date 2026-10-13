from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views import View

from apps.automation.models import AutoTicketRule
from apps.core.mixins import CompanyMemberRequiredMixin
from apps.products.access import accessible_products
from apps.uiapi.shell import render_shell


class RuleShellView(CompanyMemberRequiredMixin, View):
    """The list and create form, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class RuleEditView(CompanyMemberRequiredMixin, View):
    """404 unless the rule is on a product the person may open (or company-wide and they are an owner or admin)."""

    def get(self, request, pk):
        allowed = Q(product__in=accessible_products(request.user, request.company))
        if request.company_role in ("owner", "admin"):
            allowed |= Q(product__isnull=True)
        get_object_or_404(AutoTicketRule.objects.filter(allowed), pk=pk, company=request.company)
        return render_shell(request)

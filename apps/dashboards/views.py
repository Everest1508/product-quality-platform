from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.products.access import require_product_access
from apps.products.models import Product
from apps.uiapi.shell import render_shell


class DashboardShellView(CompanyMemberRequiredMixin, View):
    """Home and reports, served by the React shell."""

    def get(self, request):
        return render_shell(request)


class AuditLogView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        return render_shell(request)


class ProductDashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request, product_pk):
        product = get_object_or_404(Product, pk=product_pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)

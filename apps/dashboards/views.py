from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dashboards.service import get_admin_dashboard_data, get_product_dashboard_data
from apps.products.models import Product


class AdminDashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        data = get_admin_dashboard_data(request.company)

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_admin_dashboard_content.html", data)

        return render(request, "dashboards/admin_dashboard.html", data)


class ProductDashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request, product_pk):
        product = get_object_or_404(
            Product.objects.select_related("company"),
            pk=product_pk,
            company=request.company,
        )
        data = get_product_dashboard_data(request.company, product)

        if request.headers.get("HX-Request") == "true":
            return render(request, "dashboards/partials/_product_dashboard_content.html", data)

        return render(request, "dashboards/product_dashboard.html", data)

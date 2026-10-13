from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.response import Response

from apps.core.context_processors import _attach_product_counts
from apps.products.access import accessible_products, require_product_access
from apps.products.models import Product
from apps.uiapi.views import CompanyAPIView

_SECTIONS = {
    "overview": "products:product_detail",
    "errors": "products:product_errors",
    "tickets": "products:product_board",
    "surveys": "products:product_surveys",
    "rules": "products:product_rules",
}


class ProductNavAPIView(CompanyAPIView):
    """The product section of the sidebar: counts, section URLs, and the product switcher."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request._request, product)
        _attach_product_counts(product)
        return Response({
            "id": product.pk,
            "name": product.name,
            "counts": {
                "errors": product.error_count,
                "tickets": product.ticket_count,
                "surveys": product.survey_count,
                "rules": product.rule_count,
            },
            "urls": {key: reverse(name, kwargs={"pk": product.pk}) for key, name in _SECTIONS.items()},
            "products": [
                {"id": p.pk, "name": p.name, "url": reverse("products:product_board", kwargs={"pk": p.pk})}
                for p in accessible_products(request.user, request.company).order_by("name")
            ],
            "all_url": reverse("products:product_list"),
        })

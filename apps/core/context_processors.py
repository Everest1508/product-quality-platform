from apps.products.models import Product


def product_context(request):
    ctx = {}
    try:
        match = request.resolver_match
        if not match:
            return ctx
        pk = match.kwargs.get("product_pk") or match.kwargs.get("pk")
        if not pk:
            return ctx
        path = request.path
        if path.startswith(f"/products/{pk}/"):
            product = Product.objects.filter(
                company=request.company,
                pk=pk,
            ).first()
            if product:
                ctx["product"] = product
    except Exception:
        pass
    return ctx

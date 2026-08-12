from apps.products.models import Product


def _attach_product_counts(product):
    from apps.ingestion.models import ErrorGroup
    from apps.tickets.models import Ticket

    product.error_count = (
        ErrorGroup.objects.filter(product=product)
        .exclude(status__in=["resolved", "ignored"])
        .count()
    )
    product.ticket_count = (
        Ticket.objects.filter(product=product)
        .exclude(status__in=["resolved", "closed"])
        .count()
    )
    product.survey_count = product.surveys.count()
    product.version_count = product.versions.count()
    product.rule_count = product.auto_ticket_rules.count()


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
                _attach_product_counts(product)
                ctx["product"] = product
    except Exception:
        pass
    return ctx


def workspace_context(request):
    if not request.user.is_authenticated:
        return {}
    memberships = request.user.memberships.select_related("company").all()
    return {"workspaces": list(memberships)}

from django.conf import settings

from apps.products.models import Product


def version_context(request):
    """The running version, for the sidebar footer.

    Cheap and unconditional: it reads one setting and parses nothing. The
    changelog itself is fetched from /api/v1/changelog/ on demand instead, so it
    is not paid for on every page.
    """
    return {"app_version": getattr(settings, "APP_VERSION", "0.0.0")}


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
                from apps.products.access import accessible_products
                nav = list(
                    accessible_products(request.user, request.company)
                    .order_by("name")
                    .values("pk", "name", "icon")
                )
                # The product you are looking at is always in its own switcher.
                if not any(p["pk"] == product.pk for p in nav):
                    nav.append({"pk": product.pk, "name": product.name, "icon": product.icon})
                    nav.sort(key=lambda p: p["name"].lower())
                ctx["nav_products"] = nav
    except Exception:
        pass
    return ctx


def workspace_context(request):
    if not request.user.is_authenticated:
        return {}

    ctx = {"workspaces": list(request.user.memberships.select_related("company").all())}

    company = getattr(request, "company", None)
    if company is not None:
        try:
            from apps.ingestion.models import ErrorGroup
            from apps.products.access import accessible_products
            from apps.tickets.models import Ticket

            products = accessible_products(request.user, company)
            ctx["nav_open_tickets"] = (
                Ticket.objects.filter(company=company)
                .filter(product__in=products)
                .exclude(status__in=["resolved", "closed"])
                .count()
            )
            ctx["nav_open_errors"] = (
                ErrorGroup.objects.filter(company=company, product__in=products)
                .exclude(status__in=["resolved", "ignored"])
                .count()
            )
            if request.company_role in ("owner", "admin"):
                from apps.attendance.models import AttendanceCorrection

                ctx["nav_pending_corrections"] = AttendanceCorrection.objects.filter(
                    company=company, status="pending"
                ).count()
                from apps.notifications.models import Notification

                ctx["nav_new_leads"] = Notification.objects.filter(
                    user=request.user, company=company, kind="lead", read_at__isnull=True
                ).count()
        except Exception:
            pass

    return ctx

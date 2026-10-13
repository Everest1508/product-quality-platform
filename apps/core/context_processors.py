from django.conf import settings

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


def nav_counts(user, company, role):
    """Sidebar badge numbers for one person in one workspace. Same rules as the
    legacy sidebar: only products the person can open, 'open' means not
    resolved/closed (tickets) or resolved/ignored (errors)."""
    from apps.attendance.models import AttendanceCorrection
    from apps.ingestion.models import ErrorGroup
    from apps.products.access import accessible_products
    from apps.tickets.models import Ticket

    products = accessible_products(user, company)
    return {
        "open_tickets": Ticket.objects.filter(company=company, product__in=products)
        .exclude(status__in=["resolved", "closed"])
        .count(),
        "open_errors": ErrorGroup.objects.filter(company=company, product__in=products)
        .exclude(status__in=["resolved", "ignored"])
        .count(),
        "pending_corrections": AttendanceCorrection.objects.filter(company=company, status="pending").count()
        if role in ("owner", "admin")
        else 0,
    }

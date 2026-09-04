from django.db.models import Exists, OuterRef, Q
from django.http import Http404

from apps.accounts.models import Membership
from apps.products.models import Product, ProductAccess


def accessible_products(user, company):
    """Return a queryset of Products the user can see within the company.

    Owners and admins see all products.
    Other roles see only products they are explicitly allocated to.
    """
    membership = Membership.objects.filter(user=user, company=company).first()
    if not membership:
        return Product.objects.none()

    if membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return Product.objects.filter(company=company)

    has_access = ProductAccess.objects.filter(
        product=OuterRef("pk"),
        user=user,
        company=company,
    )
    return Product.objects.filter(company=company).filter(Exists(has_access))


def user_has_product_access(user, company, product):
    """Check if a specific user has access to a specific product."""
    membership = Membership.objects.filter(user=user, company=company).first()
    if not membership:
        return False

    if membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return True

    return ProductAccess.objects.filter(
        product=product,
        user=user,
        company=company,
    ).exists()


def require_product_access(request, product):
    """Raise Http404 if the user doesn't have access to the product."""
    if not user_has_product_access(request.user, request.company, product):
        raise Http404


def accessible_tickets(user, company):
    """Return a queryset of Tickets the user can see within the company.

    A ticket is visible if it has no product, or if it belongs to a product the
    user is allowed to see. Owners and admins see every ticket.
    """
    from apps.tickets.models import Ticket

    return Ticket.objects.filter(company=company).filter(
        Q(product__isnull=True) | Q(product__in=accessible_products(user, company))
    )


def require_ticket_access(request, ticket):
    """Raise Http404 if the ticket belongs to a product the user can't access."""
    if ticket.product_id and not user_has_product_access(
        request.user, request.company, ticket.product
    ):
        raise Http404


def accessible_error_groups(user, company):
    """Return a queryset of ErrorGroups the user can see within the company.

    ErrorGroups always belong to a product, so visibility follows product access.
    Owners and admins see every error group.
    """
    from apps.ingestion.models import ErrorGroup

    return ErrorGroup.objects.filter(
        company=company, product__in=accessible_products(user, company)
    )


def require_error_group_access(request, error_group):
    """Raise Http404 if the error group's product isn't accessible to the user."""
    if not user_has_product_access(
        request.user, request.company, error_group.product
    ):
        raise Http404


def product_users(product, company):
    """Return users who have access to this product (for assignee filtering).

    Owners and admins always have access. Other roles need a ProductAccess record.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    membership = Membership.objects.filter(user=OuterRef("pk"), company=company)
    is_owner_or_admin = membership.filter(role__in=[Membership.Role.OWNER, Membership.Role.ADMIN])
    has_access = ProductAccess.objects.filter(
        product=product, user=OuterRef("pk"), company=company,
    )
    return User.objects.filter(
        memberships__company=company,
    ).filter(Exists(is_owner_or_admin) | Exists(has_access)).order_by("username").distinct()

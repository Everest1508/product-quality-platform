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

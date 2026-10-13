from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.context_processors import _attach_product_counts
from apps.products import service
from apps.products.access import accessible_products, require_product_access
from apps.products.models import APIKey, Product, ProductMilestone, ProductVersion
from apps.uiapi.tickets import form_errors
from apps.uiapi.views import CompanyAPIView

PER_PAGE = 25
SORTS = {
    "name": "name", "-name": "-name", "created": "created_at", "-created": "-created_at",
    "versions": "version_count", "-versions": "-version_count",
}

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


def _is_admin(request):
    return request.company_role in ("owner", "admin")


def _require_admin(request):
    if not _is_admin(request):
        raise PermissionDenied("Only owners and admins can do this.")


def _product(request, pk):
    """A product in this company the user may open, else 404."""
    product = get_object_or_404(Product, pk=pk, company=request.company)
    require_product_access(request._request, product)
    return product


def _key_manager(request, product):
    if request.company_role not in service.KEY_MANAGER_ROLES:
        raise PermissionDenied("Only owners, admins and developers can manage API keys.")


def key_json(k):
    return {
        "id": k.pk, "name": k.name, "prefix": k.prefix, "state": k.state, "usable": k.is_usable,
        "created_at": k.created_at.isoformat(),
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
    }


def _name(u):
    return u.get_full_name() or u.username


def product_detail_json(request, product, **extra):
    product = Product.objects.get(pk=product.pk)
    _attach_product_counts(product)
    admin = _is_admin(request)
    members = []
    if admin:
        allocated = set(product.access_records.values_list("user_id", flat=True))
        members = [
            {"id": u.pk, "name": _name(u), "username": u.username, "email": u.email,
             "allocated": u.pk in allocated, "is_you": u.pk == request.user.pk}
            for u in get_user_model().objects.filter(memberships__company=request.company).order_by("username")
        ]
    return {
        "product": {
            "id": product.pk, "name": product.name, "slug": product.slug, "key": product.key,
            "description": product.description, "default_environment": product.default_environment,
            "created_at": product.created_at.isoformat(),
            "webhook_configured": bool(product.discord_webhook_url),
            # The secret only travels to people who can edit it.
            "discord_webhook_url": product.discord_webhook_url if admin else "",
            "counts": {"errors": product.error_count, "tickets": product.ticket_count,
                       "surveys": product.survey_count, "versions": product.version_count},
        },
        "milestones": [
            {"id": m.pk, "title": m.title, "order": m.order, "target_date": m.target_date.isoformat(),
             "status": m.computed_status, "tickets": m.tickets.count()}
            for m in product.milestones.all()
        ],
        "versions": [
            {"id": v.pk, "version_string": v.version_string, "is_current": v.is_current,
             "released_at": v.released_at.isoformat() if v.released_at else None}
            for v in product.versions.all()
        ],
        "api_keys": [key_json(k) for k in product.api_keys.all()],
        "can_manage_keys": request.company_role in service.KEY_MANAGER_ROLES,
        "is_admin": admin,
        "members": members,
        **extra,
    }


class ProductListAPIView(CompanyAPIView):
    def get(self, request):
        from apps.dashboards.service import _build_product_cards
        from apps.ingestion.models import ErrorOccurrence

        q = request.query_params
        qs = accessible_products(request.user, request.company)
        search = q.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        sort = q.get("sort", "name")
        if sort in ("versions", "-versions"):
            qs = qs.annotate(version_count=Count("versions"))
        page = Paginator(qs.order_by(SORTS.get(sort, "name")), PER_PAGE).get_page(q.get("page", 1))

        # Cards for everything the person can open, so the tiles are the whole workspace, not the page.
        all_ids = list(accessible_products(request.user, request.company).values_list("pk", flat=True))
        cards = {c["product"].pk: c for c in _build_product_cards(request.company, all_ids)}
        summary = {
            "products": len(all_ids),
            "open_errors": sum(c["open_errors"] for c in cards.values()),
            "open_tickets": sum(c["open_tickets"] for c in cards.values()),
            "attention": sum(1 for c in cards.values() if c["health"] != "healthy"),
        }
        since = timezone.localdate() - timedelta(days=6)
        daily = {}
        for pid, day, n in (
            ErrorOccurrence.objects.filter(
                company=request.company, error_group__product_id__in=[p.pk for p in page], created_at__date__gte=since
            )
            .values_list("error_group__product_id", "created_at__date").annotate(n=Count("pk")).order_by()
        ):
            daily[(pid, day)] = n
        items = []
        for p in page:
            card = cards.get(p.pk, {"open_errors": 0, "open_tickets": 0, "health": "healthy"})
            series = [daily.get((p.pk, since + timedelta(days=i)), 0) for i in range(7)]
            peak = max(series) or 1
            items.append({
                "id": p.pk, "name": p.name, "key": p.key, "slug": p.slug, "description": p.description,
                "health": card["health"], "open_errors": card["open_errors"], "open_tickets": card["open_tickets"],
                "version_count": p.versions.count(), "api_key_count": p.api_keys.count(),
                "spark": [max(8, round(n * 100 / peak)) if n else 4 for n in series], "week_errors": sum(series),
                "url": reverse("products:product_detail", kwargs={"pk": p.pk}),
                "dashboard_url": reverse("dashboards:product_dashboard", kwargs={"product_pk": p.pk}),
            })
        return Response({
            "items": items, "summary": summary, "can_create": _is_admin(request),
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
        })

    def post(self, request):
        _require_admin(request)
        data = request.data
        product, form = service.create_product(data, data.get("milestones"), request.user, request.company)
        if product is None:
            return Response(form_errors(form), status=400)
        return Response(
            {"id": product.pk, "url": reverse("products:product_detail", kwargs={"pk": product.pk}),
             "message": f"Product '{product.name}' created."},
            status=201,
        )


class ProductKeySuggestAPIView(CompanyAPIView):
    def get(self, request):
        _require_admin(request)
        exclude = request.query_params.get("product", "")
        key = service.suggest_key(request.company, request.query_params.get("name", ""), int(exclude) if exclude.isdecimal() else None)
        return Response({"key": key})


class ProductDetailAPIView(CompanyAPIView):
    def get(self, request, pk):
        return Response(product_detail_json(request, _product(request, pk)))

    def patch(self, request, pk):
        _require_admin(request)
        product = _product(request, pk)
        saved, form = service.update_product(request.data, request.data.get("milestones"), product, request.user, request.company)
        if saved is None:
            return Response(form_errors(form), status=400)
        return Response(product_detail_json(request, saved, message=f"Product '{saved.name}' updated."))

    def delete(self, request, pk):
        _require_admin(request)
        product = _product(request, pk)
        return Response({"deleted": service.delete_product(product, request.user, request.company)})


class ProductVersionAPIView(CompanyAPIView):
    def post(self, request, pk):
        product = _product(request, pk)
        version, form = service.add_version(request.data, product, request.user, request.company)
        if version is None:
            return Response(form_errors(form), status=400)
        return Response(product_detail_json(request, product, message=f"Version '{version.version_string}' added."))

    def delete(self, request, pk, version_pk):
        product = _product(request, pk)
        version = get_object_or_404(product.versions, pk=version_pk)
        text = service.delete_version(version, request.user, request.company)
        return Response(product_detail_json(request, product, message=f"Version '{text}' deleted."))


class ProductKeyCreateAPIView(CompanyAPIView):
    def post(self, request, pk):
        product = _product(request, pk)
        _key_manager(request, product)
        key, raw = service.create_key(product, request.data.get("name"), request.user, request.company)
        return Response(product_detail_json(request, product, raw_key=raw, message=f"API key '{key.name}' created."))


def _key(request, pk):
    key = get_object_or_404(APIKey.objects.select_related("product"), pk=pk, product__company=request.company)
    require_product_access(request._request, key.product)
    _key_manager(request, key.product)
    return key


class ProductKeyRevokeAPIView(CompanyAPIView):
    def post(self, request, pk):
        key = _key(request, pk)
        service.revoke_key(key, request.user, request.company)
        return Response(product_detail_json(request, key.product, message=f"API key '{key.name}' revoked."))


class ProductKeyRotateAPIView(CompanyAPIView):
    def post(self, request, pk):
        old = _key(request, pk)
        new, raw, message = service.rotate_key(old, request.data.get("grace", "1d"), request.user, request.company)
        if new is None:
            return Response({"detail": message}, status=400)
        return Response(product_detail_json(request, old.product, raw_key=raw, message=message))


class ProductAccessAPIView(CompanyAPIView):
    def post(self, request, pk):
        product = _product(request, pk)
        if not _is_admin(request):
            raise Http404
        error = service.grant_access(product, request.data.get("user_id"), request.user, request.company)
        if error:
            return Response({"detail": error}, status=400)
        return Response(product_detail_json(request, product, message="Access granted."))

    def delete(self, request, pk, user_pk):
        product = _product(request, pk)
        if not _is_admin(request):
            raise Http404
        target = get_object_or_404(get_user_model(), pk=user_pk, memberships__company=request.company)
        service.revoke_access(product, target, request.user, request.company)
        return Response(product_detail_json(request, product, message="Access removed."))


class ProductMilestoneAddAPIView(CompanyAPIView):
    def post(self, request, pk):
        from datetime import datetime

        product = _product(request, pk)
        title = request.data.get("title")
        title = title.strip() if isinstance(title, str) else ""
        try:
            target = datetime.strptime(str(request.data.get("target_date", "")), "%Y-%m-%d").date()
            order = min(int(request.data.get("order") or product.milestones.count() + 1), 100000)
        except (ValueError, TypeError):
            return Response({"detail": "Enter a title, a valid date and a number for the order."}, status=400)
        if not title:
            return Response({"detail": "Enter a title, a valid date and a number for the order."}, status=400)
        service.add_milestone(product, title[:255], target, max(order, 1), request.user, request.company)
        return Response(product_detail_json(request, product, message=f"Milestone '{title}' added to flowchart."))


def _milestone(request, pk):
    m = get_object_or_404(ProductMilestone.objects.select_related("product"), pk=pk, company=request.company)
    require_product_access(request._request, m.product)
    return m


class ProductMilestoneToggleAPIView(CompanyAPIView):
    def post(self, request, pk):
        m = _milestone(request, pk)
        service.toggle_milestone(m, request.user, request.company)
        return Response(product_detail_json(request, m.product, message=f"\"{m.title}\" is now {m.get_status_display().lower()}."))


class ProductMilestoneDeleteAPIView(CompanyAPIView):
    def delete(self, request, pk):
        m = _milestone(request, pk)
        product, title = m.product, m.title
        service.delete_milestone(m, request.user, request.company)
        return Response(product_detail_json(request, product, message=f"Milestone \"{title}\" deleted."))


class ProductApiDocsAPIView(CompanyAPIView):
    """How to send errors, feedback and tickets to this product, with the real field lists and snippets."""

    def get(self, request, pk):
        from apps.ingestion import docs

        product = _product(request, pk)
        base = request.build_absolute_uri("/")
        return Response({
            "product": {"id": product.pk, "name": product.name},
            "base_url": base,
            "endpoints": docs.build(base),
            "error_codes": [list(e) for e in docs.ERRORS],
            "keys": [key_json(k) for k in product.api_keys.all()],
            "can_manage_keys": request.company_role in service.KEY_MANAGER_ROLES,
        })

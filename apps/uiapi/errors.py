from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.errors import service as error_service
from apps.errors import trends
from apps.errors.forms import ErrorCreateForm
from apps.ingestion.models import ErrorGroup
from apps.products.access import (
    accessible_error_groups,
    accessible_products,
    accessible_tickets,
    require_error_group_access,
)
from apps.uiapi.tickets import form_errors, scoped_product
from apps.uiapi.views import CompanyAPIView

PER_PAGE = 25
OPEN_EXCLUDED = ("resolved", "ignored")
SORTS = {
    "last_seen": "last_seen", "-last_seen": "-last_seen",
    "severity": "severity", "-severity": "-severity",
    "count": "occurrence_count", "-count": "-occurrence_count",
    "title": "title", "-title": "-title",
}
STATUS_MESSAGES = {"resolved": "Error group resolved.", "ignored": "Error group ignored."}


def error_url(group):
    return f"/products/{group.product_id}/errors/{group.pk}/"


def _can_delete(role):
    return role in ("owner", "admin")


def error_json(group, role):
    """One row of the list. `attach_trends` must already have run for the trend and flags."""
    trend = group.trend
    return {
        "id": group.pk,
        "title": group.title,
        "fingerprint": group.fingerprint,
        "severity": group.severity,
        "severity_label": group.get_severity_display(),
        "status": group.status,
        "status_label": group.get_status_display(),
        "product": {"id": group.product_id, "name": group.product.name},
        "occurrence_count": group.occurrence_count,
        "last_seen": group.last_seen.isoformat(),
        "is_regression": group.is_regression,
        "regressed_at": group.regressed_at.isoformat() if group.regressed_at else None,
        "new_in_release": group.first_version_label if group.new_in_release else "",
        "trend": {k: trend[k] for k in ("total", "line", "area", "width", "height", "rising")},
        "can_delete": _can_delete(role),
        "url": error_url(group),
    }


def _group(request, pk):
    """A group in this company whose product the user may open, else 404."""
    group = get_object_or_404(ErrorGroup.objects.select_related("product", "first_version"), pk=pk, company=request.company)
    require_error_group_access(request._request, group)
    return group


def detail_json(request, group, **extra):
    group = trends.attach_trends([group])[0]
    tickets = (
        accessible_tickets(request.user, request.company)
        .filter(linked_error_group=group)
        .select_related("product")
        .order_by("-created_at")
    )
    occurrences = group.occurrences.select_related("version")[:50]
    base = error_json(group, request.company_role)
    trend = trends.detail_trend(group)
    return {
        "error": {
            **base,
            "error_type": group.error_type,
            "affected_user_count": group.affected_user_count,
            "first_seen": group.first_seen.isoformat(),
            "regression_count": group.regression_count,
            "first_version": group.first_version.version_string if group.first_version_id else "",
        },
        "occurrences": [
            {
                "id": o.pk,
                "created_at": o.created_at.isoformat(),
                "environment": o.environment,
                "version": o.version.version_string if o.version_id else "",
                "user_ref": o.user_ref,
                "stacktrace": o.stacktrace,
            }
            for o in occurrences
        ],
        "trend": {**trend, "bars": [{**b, "date": b["date"].isoformat()} for b in trend["bars"]]},
        "linked_tickets": [
            {
                "id": t.pk, "key": t.key, "title": t.title, "status": t.status,
                "status_label": t.get_status_display(),
                "url": f"/products/{t.product_id}/tickets/{t.pk}/" if t.product_id else f"/tickets/{t.pk}/",
            }
            for t in tickets
        ],
        "statuses": [list(c) for c in ErrorGroup.STATUS_CHOICES],
        **extra,
    }


class ErrorListAPIView(CompanyAPIView):
    def get(self, request):
        q = request.query_params
        product = scoped_product(request)
        qs = product.error_groups.all() if product else accessible_error_groups(request.user, request.company)
        qs = qs.select_related("product", "first_version")

        if not product and q.get("product", "").isdecimal():
            qs = qs.filter(product_id=int(q["product"]))
        if q.get("status"):
            qs = qs.filter(status=q["status"])
        if q.get("severity"):
            qs = qs.filter(severity=q["severity"])
        search = q.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        # Counted before the tab narrows the list, so the badge always shows how many exist.
        regressed_count = qs.filter(regression_count__gt=0).count()
        if q.get("regressed") == "1":
            qs = qs.filter(regression_count__gt=0)
        qs = qs.order_by(SORTS.get(q.get("sort", ""), "-last_seen"))

        page = Paginator(qs, PER_PAGE).get_page(q.get("page", 1))
        items = trends.attach_trends(page.object_list)
        return Response({
            "items": [error_json(g, request.company_role) for g in items],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
            "open_count": qs.exclude(status__in=OPEN_EXCLUDED).count(),
            "regressed_count": regressed_count,
        })

    def post(self, request):
        """Report an error by hand. The product must be one the user can open."""
        form = ErrorCreateForm(request.data, company=request.company, user=request.user)
        if not form.is_valid():
            return Response(form_errors(form), status=400)
        group = form.save(company=request.company, user=request.user)
        return Response({"id": group.pk, "url": error_url(group), "message": f"Error #{group.pk} created."}, status=201)


class ErrorMetaAPIView(CompanyAPIView):
    """Choices for the filter bar and the report form."""

    def get(self, request):
        product = scoped_product(request)
        products = [] if product else [
            {"id": p.pk, "name": p.name} for p in accessible_products(request.user, request.company).order_by("name")
        ]
        return Response({
            "statuses": [list(c) for c in ErrorGroup.STATUS_CHOICES],
            "severities": [list(c) for c in ErrorGroup.SEVERITY_CHOICES],
            "products": products,
        })


class ErrorDetailAPIView(CompanyAPIView):
    def get(self, request, pk):
        return Response(detail_json(request, _group(request, pk)))

    def delete(self, request, pk):
        group = _group(request, pk)
        if not _can_delete(request.company_role):
            raise PermissionDenied("Only owners and admins can delete errors.")
        return Response({"deleted": error_service.delete_error(group, request.user, request.company)})


class ErrorStatusAPIView(CompanyAPIView):
    def post(self, request, pk):
        group = _group(request, pk)
        new = request.data.get("status")
        if not isinstance(new, str):
            return Response({"detail": "Choose a status."}, status=400)
        error = error_service.set_status(group, new, request.user, request.company)
        if error:
            return Response({"detail": error}, status=400)
        message = STATUS_MESSAGES.get(new, f"Status changed to '{new}'.")
        return Response(detail_json(request, group, message=message))


class ErrorConvertAPIView(CompanyAPIView):
    def post(self, request, pk):
        group = _group(request, pk)
        ticket = error_service.convert_to_ticket(group, request.user, request.company)
        return Response(detail_json(
            request, group,
            ticket={"id": ticket.pk, "key": ticket.key},
            message=f"Ticket {ticket.key} created from error #{group.pk}.",
        ))

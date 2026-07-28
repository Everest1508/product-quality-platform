from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.errors.forms import ErrorCreateForm
from apps.ingestion.models import ErrorGroup, ErrorOccurrence


def _error_redirect(error_group):
    if error_group.product_id:
        return "products:product_error_detail", {"pk": error_group.product_id, "error_pk": error_group.pk}
    return "errors:error_detail", {"pk": error_group.pk}


ERROR_SORT_MAP = {
    "last_seen": "last_seen",
    "-last_seen": "-last_seen",
    "severity": "severity",
    "-severity": "-severity",
    "count": "occurrence_count",
    "-count": "-occurrence_count",
    "title": "title",
    "-title": "-title",
}


class ErrorListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = ErrorGroup.objects.filter(company=request.company).select_related("product")

        product_id = request.GET.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        severity = request.GET.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        sort = request.GET.get("sort", "-last_seen")
        order = ERROR_SORT_MAP.get(sort, "-last_seen")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page_num = request.GET.get("page", 1)
        page = paginator.get_page(page_num)

        products = request.company.product_set.all()

        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_error_list_body.html", {
                "page": page,
            })

        return render(request, "errors/error_list.html", {
            "page": page,
            "products": products,
            "current_product": product_id,
            "current_status": status,
            "current_severity": severity,
            "search": search,
            "current_sort": sort,
        })


class ErrorDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        error_group = get_object_or_404(
            ErrorGroup.objects.select_related("product"),
            pk=pk,
            company=request.company,
        )
        occurrences = error_group.occurrences.all()[:50]

        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_occurrence_list.html", {
                "occurrences": occurrences,
            })

        return render(request, "errors/error_detail.html", {
            "error_group": error_group,
            "occurrences": occurrences,
            "status_choices": ErrorGroup.STATUS_CHOICES,
        })


class ErrorStatusView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        error_group = get_object_or_404(
            ErrorGroup,
            pk=pk,
            company=request.company,
        )
        new_status = request.POST.get("status")
        valid_choices = [c[0] for c in ErrorGroup.STATUS_CHOICES]
        if new_status in valid_choices:
            error_group.status = new_status
            error_group.save(update_fields=["status"])
            messages.success(request, f"Status changed to '{new_status}'.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_error_status_badge.html", {
                "error_group": error_group,
            })
        url_name, kwargs = _error_redirect(error_group)
        return redirect(url_name, **kwargs)


class ErrorIgnoreView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        error_group = get_object_or_404(
            ErrorGroup,
            pk=pk,
            company=request.company,
        )
        error_group.status = "ignored"
        error_group.save(update_fields=["status"])
        messages.success(request, "Error group ignored.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_error_status_badge.html", {
                "error_group": error_group,
            })
        url_name, kwargs = _error_redirect(error_group)
        return redirect(url_name, **kwargs)


class ErrorResolveView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        error_group = get_object_or_404(
            ErrorGroup,
            pk=pk,
            company=request.company,
        )
        error_group.status = "resolved"
        error_group.save(update_fields=["status"])
        messages.success(request, "Error group resolved.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "errors/partials/_error_status_badge.html", {
                "error_group": error_group,
            })
        url_name, kwargs = _error_redirect(error_group)
        return redirect(url_name, **kwargs)


class ErrorCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        initial = {}
        product_id = request.GET.get("product")
        if product_id:
            initial["product"] = product_id
        form = ErrorCreateForm(company=request.company, initial=initial)
        return render(request, "errors/error_form.html", {"form": form})

    def post(self, request):
        form = ErrorCreateForm(request.POST, company=request.company)
        if form.is_valid():
            group = form.save(company=request.company, user=request.user)
            messages.success(request, f"Error #{group.pk} created.")
            url_name, kwargs = _error_redirect(group)
            return redirect(url_name, **kwargs)
        return render(request, "errors/error_form.html", {"form": form})

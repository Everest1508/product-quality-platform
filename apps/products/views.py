from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.context_processors import _attach_product_counts
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.products.access import require_product_access
from apps.products.models import Product
from apps.uiapi.shell import render_shell


class ProductShellView(CompanyMemberRequiredMixin, View):
    """Pages that need no product (the list), served by the React shell."""

    def get(self, request):
        return render_shell(request)


class ProductAdminShellView(CompanyAdminRequiredMixin, View):
    """The create form: owners and admins only, as before."""

    def get(self, request):
        return render_shell(request)


class ProductPageView(CompanyMemberRequiredMixin, View):
    """Detail and API docs: 404 unless the person may open the product."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductEditView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductErrorShellView(CompanyMemberRequiredMixin, View):
    """A product's error list and report form, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductErrorDetailView(CompanyMemberRequiredMixin, View):
    """One error of a product, served by the React shell. 404 unless the error belongs to this product."""

    def get(self, request, pk, error_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        get_object_or_404(product.error_groups, pk=error_pk)
        return render_shell(request)


class ProductTicketListView(CompanyMemberRequiredMixin, View):
    """A product's ticket list, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductTicketKanbanView(CompanyMemberRequiredMixin, View):
    """A product's ticket board, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductTicketCreateView(CompanyMemberRequiredMixin, View):
    """A product's new-ticket form, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)




class ProductTicketDetailView(CompanyMemberRequiredMixin, View):
    """A ticket under its product, served by the React shell. The ticket must belong to that product."""

    def get(self, request, pk, ticket_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        get_object_or_404(product.tickets, pk=ticket_pk)
        return render_shell(request)


class ProductSurveyListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        qs = product.surveys.select_related("created_by")

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        survey_type = request.GET.get("type")
        if survey_type:
            qs = qs.filter(survey_type=survey_type)
        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        sort = request.GET.get("sort", "-created")
        sort_map = {"created": "created_at", "-created": "-created_at", "name": "name", "-name": "-name", "responses": "response_count", "-responses": "-response_count"}
        qs = qs.order_by(sort_map.get(sort, "-created_at"))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_survey_list_body.html", {"page": page})

        return render(request, "products/product_survey_list.html", {
            "page": page, "product": product,
            "current_status": status, "current_type": survey_type,
            "search": search, "current_sort": sort,
        })


class ProductSurveyCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.feedback.forms import SurveyCreateForm
        form = SurveyCreateForm(company=request.company, initial={"product": product})
        return render(request, "products/product_survey_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.feedback.forms import SurveyCreateForm
        form = SurveyCreateForm(request.POST, company=request.company)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.company = request.company
            survey.created_by = request.user
            survey.product = product
            survey.save()
            log_activity(
                request.company, "survey_created",
                f"Survey '{survey.name}' created for {product.name}",
                actor=request.user,
                target_content_type="survey",
                target_object_id=survey.pk,
                metadata={"product_id": product.pk},
            )
            messages.success(request, f"Survey '{survey.name}' created.")
            return redirect("products:product_surveys", pk=product.pk)
        return render(request, "products/product_survey_form.html", {"form": form, "product": product})


class ProductRuleListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        qs = product.auto_ticket_rules.select_related("assign_to")

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        active = request.GET.get("active")
        if active == "1":
            qs = qs.filter(is_active=True)
        elif active == "0":
            qs = qs.filter(is_active=False)

        sort = request.GET.get("sort", "-created")
        sort_map = {"created": "created_at", "-created": "-created_at", "name": "name", "-name": "-name", "-fired": "-trigger_count"}
        qs = qs.order_by(sort_map.get(sort, "-created_at"))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_rule_list_body.html", {"page": page})

        return render(request, "products/product_rule_list.html", {
            "page": page, "product": product,
            "search": search, "current_active": active, "current_sort": sort,
        })


class ProductRuleCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.automation.forms import AutoTicketRuleForm
        form = AutoTicketRuleForm(company=request.company, initial={"product": product})
        return render(request, "products/product_rule_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.automation.forms import AutoTicketRuleForm
        form = AutoTicketRuleForm(request.POST, company=request.company)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.company = request.company
            rule.product = product
            rule.save()
            log_activity(
                request.company, "rule_created",
                f"Rule '{rule.name}' created",
                actor=request.user,
                target_content_type="rule",
                target_object_id=rule.pk,
                metadata={"product_id": product.pk},
            )
            messages.success(request, f"Rule '{rule.name}' created.")
            return redirect("products:product_rules", pk=product.pk)
        return render(request, "products/product_rule_form.html", {"form": form, "product": product})

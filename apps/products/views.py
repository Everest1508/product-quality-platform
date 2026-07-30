from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.products.access import accessible_products, require_product_access
from apps.products.forms import ProductCreateForm, ProductEditForm, VersionCreateForm
from apps.products.models import APIKey, Product, ProductAccess, ProductVersion
from apps.products.webhook import notify_ticket_created


PRODUCT_SORT_MAP = {
    "name": "name",
    "-name": "-name",
    "created": "created_at",
    "-created": "-created_at",
    "versions": "version_count",
    "-versions": "-version_count",
}


class ProductListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = accessible_products(request.user, request.company)

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        sort = request.GET.get("sort", "name")
        if sort in ("versions", "-versions"):
            qs = qs.annotate(version_count=Count("versions"))
        order = PRODUCT_SORT_MAP.get(sort, "name")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_list_body.html", {
                "page": page,
            })

        return render(request, "products/product_list.html", {
            "page": page,
            "search": search,
            "current_sort": sort,
        })


class ProductCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = ProductCreateForm()
        return render(request, "products/product_form.html", {"form": form, "editing": False})

    def post(self, request):
        form = ProductCreateForm(request.POST, company=request.company)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"Product '{product.name}' created.")
            return redirect("products:product_detail", pk=product.pk)
        return render(request, "products/product_form.html", {"form": form, "editing": False})


class ProductDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        all_members = User.objects.filter(memberships__company=request.company).order_by("username")
        allocated_ids = set(product.access_records.values_list("user_id", flat=True))
        from apps.accounts.models import Membership
        is_privileged = Membership.objects.filter(
            user=request.user, company=request.company
        ).values_list("role", flat=True).first() in (Membership.Role.OWNER, Membership.Role.ADMIN)
        versions = product.versions.all()
        api_keys = product.api_keys.all()
        return render(request, "products/product_detail.html", {
            "product": product,
            "versions": versions,
            "api_keys": api_keys,
            "all_members": all_members,
            "allocated_ids": allocated_ids,
            "is_privileged": is_privileged,
        })


class ProductEditView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        form = ProductEditForm(instance=product)
        return render(request, "products/product_form.html", {"form": form, "editing": True, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        form = ProductEditForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect("products:product_detail", pk=product.pk)
        return render(request, "products/product_form.html", {"form": form, "editing": True, "product": product})


class ProductDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        name = product.name
        product.delete()
        messages.success(request, f"Product '{name}' deleted.")
        return redirect("products:product_list")


class APIKeyCreateView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        name = request.POST.get("name", "default")
        api_key, raw_key = APIKey.create_key(product=product, name=name)
        return render(request, "products/partials/_api_key_created.html", {
            "raw_key": raw_key,
            "api_key": api_key,
        })


class APIKeyRevokeView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        api_key = get_object_or_404(APIKey, pk=pk, product__company=request.company)
        api_key.is_active = False
        api_key.revoked_at = timezone.now()
        api_key.save(update_fields=["is_active", "revoked_at"])
        messages.success(request, f"API key '{api_key.name}' revoked.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_api_key_row.html", {"api_key": api_key})
        return redirect("products:product_detail", pk=api_key.product.pk)


class VersionCreateView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        form = VersionCreateForm(request.POST)
        if form.is_valid():
            version = form.save(commit=False)
            version.product = product
            version.company = request.company
            if version.is_current:
                product.versions.filter(is_current=True).update(is_current=False)
            version.save()
            messages.success(request, f"Version '{version.version_string}' added.")

        if request.headers.get("HX-Request") == "true":
            versions = product.versions.all()
            return render(request, "products/partials/_version_list.html", {"versions": versions})
        return redirect("products:product_detail", pk=product.pk)


class VersionDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk, version_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        version = get_object_or_404(product.versions, pk=version_pk)
        version.delete()
        messages.success(request, f"Version '{version.version_string}' deleted.")

        if request.headers.get("HX-Request") == "true":
            versions = product.versions.all()
            return render(request, "products/partials/_version_list.html", {"versions": versions})
        return redirect("products:product_detail", pk=product.pk)


# ── Product-scoped views ──────────────────────────────────────────

class ProductErrorListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        qs = product.error_groups.all()

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
        sort_map = {"last_seen": "last_seen", "-last_seen": "-last_seen", "severity": "severity", "-severity": "-severity", "count": "occurrence_count", "-count": "-occurrence_count", "title": "title", "-title": "-title"}
        qs = qs.order_by(sort_map.get(sort, "-last_seen"))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_error_list_body.html", {"page": page})

        return render(request, "products/product_error_list.html", {
            "page": page, "product": product,
            "current_status": status, "current_severity": severity,
            "search": search, "current_sort": sort,
        })


class ProductErrorDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk, error_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        error_group = get_object_or_404(product.error_groups.select_related("product"), pk=error_pk)
        occurrences = error_group.occurrences.all()[:50]
        return render(request, "products/product_error_detail.html", {
            "product": product, "error_group": error_group, "occurrences": occurrences,
            "status_choices": error_group.STATUS_CHOICES,
        })


class ProductErrorCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.errors.forms import ErrorCreateForm
        form = ErrorCreateForm(company=request.company, initial={"product": product})
        return render(request, "products/product_error_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.errors.forms import ErrorCreateForm
        form = ErrorCreateForm(request.POST, company=request.company)
        if form.is_valid():
            group = form.save(company=request.company, user=request.user)
            messages.success(request, f"Error #{group.pk} created.")
            return redirect("products:product_error_detail", pk=product.pk, error_pk=group.pk)
        return render(request, "products/product_error_form.html", {"form": form, "product": product})


class ProductTicketListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        from apps.accounts.models import User
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        qs = product.tickets.select_related("assigned_to", "created_by")

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        ticket_type = request.GET.get("type")
        if ticket_type:
            qs = qs.filter(ticket_type=ticket_type)
        priority = request.GET.get("priority")
        if priority:
            qs = qs.filter(priority=priority)
        assigned = request.GET.get("assigned")
        if assigned == "me":
            qs = qs.filter(assigned_to=request.user)
        elif assigned == "unassigned":
            qs = qs.filter(assigned_to__isnull=True)
        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        sort = request.GET.get("sort", "-created")
        sort_map = {"created": "created_at", "-created": "-created_at", "updated": "updated_at", "-updated": "-updated_at", "priority": "priority", "-priority": "-priority", "title": "title", "-title": "-title"}
        qs = qs.order_by(sort_map.get(sort, "-created_at"))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        members = User.objects.filter(memberships__company=request.company).order_by("username")

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_ticket_list_body.html", {"page": page})

        return render(request, "products/product_ticket_list.html", {
            "page": page, "product": product, "members": members,
            "current_status": status, "current_type": ticket_type,
            "current_priority": priority, "current_assigned": assigned,
            "search": search, "current_sort": sort,
        })


class ProductTicketKanbanView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        from apps.tickets.models import Ticket
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        qs = product.tickets.select_related("assigned_to", "created_by")

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        columns = []
        for status_val, status_label in Ticket.Status.choices:
            col_qs = qs.filter(status=status_val).order_by("-priority", "-created_at")
            columns.append({"key": status_val, "label": status_label, "tickets": col_qs})

        return render(request, "products/product_ticket_kanban.html", {
            "product": product,
            "columns": columns,
            "search": search,
            "total": qs.count(),
            "status_choices": Ticket.Status.choices,
        })


class ProductTicketCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.tickets.forms import TicketCreateForm
        form = TicketCreateForm(company=request.company, initial={"product": product})
        return render(request, "products/product_ticket_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        from apps.tickets.forms import TicketCreateForm
        form = TicketCreateForm(request.POST, company=request.company)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = request.company
            ticket.created_by = request.user
            ticket.product = product
            ticket.source = "manual"
            ticket.save()
            notify_ticket_created(ticket)
            messages.success(request, f"Ticket #{ticket.pk} created.")
            return redirect("products:product_ticket_detail", pk=product.pk, ticket_pk=ticket.pk)
        return render(request, "products/product_ticket_form.html", {"form": form, "product": product})


class ProductTicketDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk, ticket_pk):
        from apps.tickets.forms import TicketCommentForm
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        ticket = get_object_or_404(
            product.tickets.select_related("assigned_to", "created_by", "linked_error_group"),
            pk=ticket_pk,
        )
        comments = ticket.comments.select_related("author").all()
        members = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(
            memberships__company=request.company
        ).order_by("username")
        return render(request, "products/product_ticket_detail.html", {
            "product": product, "ticket": ticket, "comments": comments,
            "comment_form": TicketCommentForm(), "members": members,
            "status_choices": __import__("apps.tickets.models", fromlist=["Ticket"]).Ticket.Status.choices,
        })


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
            messages.success(request, f"Rule '{rule.name}' created.")
            return redirect("products:product_rules", pk=product.pk)
        return render(request, "products/product_rule_form.html", {"form": form, "product": product})


# ── Product access management ─────────────────────────────────────

def _require_privileged(request):
    """Only owners and admins can manage product access."""
    from django.http import Http404
    from apps.accounts.models import Membership
    role = Membership.objects.filter(
        user=request.user, company=request.company
    ).values_list("role", flat=True).first()
    if role not in (Membership.Role.OWNER, Membership.Role.ADMIN):
        raise Http404


class ProductAccessAddView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _require_privileged(request)
        user_id = request.POST.get("user_id")
        if not user_id:
            messages.error(request, "No user selected.")
            return redirect("products:product_detail", pk=product.pk)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_user = get_object_or_404(User, pk=user_id)

        from apps.accounts.models import Membership
        if not Membership.objects.filter(user=target_user, company=request.company).exists():
            messages.error(request, "User is not a team member.")
            return redirect("products:product_detail", pk=product.pk)

        obj, created = ProductAccess.objects.get_or_create(
            product=product,
            user=target_user,
            company=request.company,
        )
        if created:
            messages.success(request, f"{target_user.username} now has access to {product.name}.")
        else:
            messages.info(request, f"{target_user.username} already has access.")

        if request.headers.get("HX-Request") == "true":
            allocated_ids = set(product.access_records.values_list("user_id", flat=True))
            all_members = User.objects.filter(memberships__company=request.company).order_by("username")
            return render(request, "products/partials/_product_access_list.html", {
                "product": product,
                "all_members": all_members,
                "allocated_ids": allocated_ids,
                "is_privileged": True,
            })
        return redirect("products:product_detail", pk=product.pk)


class ProductAccessRemoveView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk, user_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _require_privileged(request)

        ProductAccess.objects.filter(
            product=product, user_id=user_pk, company=request.company
        ).delete()
        messages.success(request, "Access removed.")

        if request.headers.get("HX-Request") == "true":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            allocated_ids = set(product.access_records.values_list("user_id", flat=True))
            all_members = User.objects.filter(memberships__company=request.company).order_by("username")
            return render(request, "products/partials/_product_access_list.html", {
                "product": product,
                "all_members": all_members,
                "allocated_ids": allocated_ids,
                "is_privileged": True,
            })
        return redirect("products:product_detail", pk=product.pk)

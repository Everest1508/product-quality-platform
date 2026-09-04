from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.context_processors import _attach_product_counts
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
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

        product_ids = [p.pk for p in page.object_list]
        from apps.dashboards.service import _build_product_cards
        cards_by_id = {c["product"].pk: c for c in _build_product_cards(request.company, product_ids)}

        for p in page.object_list:
            p.card_data = cards_by_id.get(p.pk, {
                "product": p, "open_errors": 0, "open_tickets": 0,
                "avg_score": None, "stale_count": 0, "health": "healthy"
            })
            p.version_cnt = getattr(p, "version_count", p.versions.count())
            p.api_key_cnt = p.api_keys.count()

        view_mode = request.GET.get("view", "grid")

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_list_body.html", {
                "page": page,
                "products": page.object_list,
                "view_mode": view_mode,
            })

        return render(request, "products/product_list.html", {
            "page": page,
            "products": page.object_list,
            "search": search,
            "current_sort": sort,
            "view_mode": view_mode,
        })


def _process_form_milestones(product, request_post):
    titles = request_post.getlist("milestone_title")
    dates = request_post.getlist("milestone_date")
    if not titles or not dates:
        return
    from datetime import datetime
    from apps.products.models import ProductMilestone
    for idx, (title, target_date_str) in enumerate(zip(titles, dates), 1):
        t = title.strip()
        if t and target_date_str:
            try:
                dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
            except ValueError:
                dt = timezone.localdate()
            ProductMilestone.objects.create(
                company=product.company,
                product=product,
                title=t,
                target_date=dt,
                order=idx,
                status=ProductMilestone.Status.UPCOMING,
            )


class ProductCreateView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        form = ProductCreateForm()
        return render(request, "products/product_form.html", {"form": form, "editing": False})

    def post(self, request):
        form = ProductCreateForm(request.POST, company=request.company)
        if form.is_valid():
            product = form.save()
            _process_form_milestones(product, request.POST)
            log_activity(
                request.company, "product_created",
                f"Product '{product.name}' created",
                description=product.description[:200],
                actor=request.user,
                target_content_type="product",
                target_object_id=product.pk,
            )
            messages.success(request, f"Product '{product.name}' created.")
            return redirect("products:product_detail", pk=product.pk)
        return render(request, "products/product_form.html", {"form": form, "editing": False})


class ProductDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        from apps.core.context_processors import _attach_product_counts
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
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
        milestones = product.milestones.all()
        return render(request, "products/product_detail.html", {
            "product": product,
            "versions": versions,
            "api_keys": api_keys,
            "milestones": milestones,
            "all_members": all_members,
            "allocated_ids": allocated_ids,
            "is_privileged": is_privileged,
        })


class ProductEditView(CompanyAdminRequiredMixin, View):
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
            _process_form_milestones(product, request.POST)
            log_activity(
                request.company, "product_updated",
                f"Product '{product.name}' updated",
                actor=request.user,
                target_content_type="product",
                target_object_id=product.pk,
            )
            messages.success(request, f"Product '{product.name}' updated.")
            return redirect("products:product_detail", pk=product.pk)
        return render(request, "products/product_form.html", {"form": form, "editing": True, "product": product})


class ProductDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        name = product.name
        product.delete()
        log_activity(
            request.company, "product_deleted",
            f"Product '{name}' deleted",
            actor=request.user,
            target_content_type="product",
            target_object_id=product.pk,
        )
        messages.success(request, f"Product '{name}' deleted.")
        return redirect("products:product_list")


class APIKeyCreateView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        name = request.POST.get("name", "default")
        api_key, raw_key = APIKey.create_key(product=product, name=name)
        log_activity(
            request.company, "api_key_created",
            f"API key '{name}' created for {product.name}",
            actor=request.user,
            target_content_type="api_key",
            target_object_id=api_key.pk,
            metadata={"product_id": product.pk},
        )
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
        log_activity(
            request.company, "api_key_revoked",
            f"API key '{api_key.name}' revoked",
            actor=request.user,
            target_content_type="api_key",
            target_object_id=api_key.pk,
            metadata={"product_id": api_key.product_id},
        )
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
            log_activity(
                request.company, "version_added",
                f"Version '{version.version_string}' added to {product.name}",
                actor=request.user,
                target_content_type="version",
                target_object_id=version.pk,
                metadata={"product_id": product.pk, "is_current": version.is_current},
            )
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
        version_string = version.version_string
        version.delete()
        log_activity(
            request.company, "version_removed",
            f"Version '{version_string}' removed from {product.name}",
            actor=request.user,
            target_content_type="version",
            target_object_id=version_pk,
            metadata={"product_id": product.pk},
        )
        messages.success(request, f"Version '{version_string}' deleted.")

        if request.headers.get("HX-Request") == "true":
            versions = product.versions.all()
            return render(request, "products/partials/_version_list.html", {"versions": versions})
        return redirect("products:product_detail", pk=product.pk)


# ── Product-scoped views ──────────────────────────────────────────

class ProductErrorListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
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
        _attach_product_counts(product)
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
        _attach_product_counts(product)
        from apps.errors.forms import ErrorCreateForm
        form = ErrorCreateForm(company=request.company, user=request.user, initial={"product": product})
        return render(request, "products/product_error_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
        from apps.errors.forms import ErrorCreateForm
        form = ErrorCreateForm(request.POST, company=request.company, user=request.user)
        if form.is_valid():
            group = form.save(company=request.company, user=request.user)
            messages.success(request, f"Error #{group.pk} created.")
            return redirect("products:product_error_detail", pk=product.pk, error_pk=group.pk)
        return render(request, "products/product_error_form.html", {"form": form, "product": product})


class ProductTicketListView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        from apps.products.access import product_users
        from apps.tickets.models import Ticket
        from apps.tickets.views import apply_ticket_filters, sort_tickets

        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)

        qs = product.tickets.select_related("assigned_to", "created_by")
        qs, ctx = apply_ticket_filters(request, qs)
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        qs = sort_tickets(request, qs, default=("-created_at",))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_ticket_list_results.html",
                          {"page": page, "product": product})

        return render(request, "products/product_ticket_list.html", {
            **ctx,
            "page": page, "product": product,
            "members": product_users(product, request.company),
            "current_status": status,
            "status_choices": Ticket.Status.choices,
        })


class ProductTicketKanbanView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        from apps.products.access import product_users
        from apps.tickets.models import Ticket
        from apps.tickets.views import apply_ticket_filters, sort_tickets

        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)

        qs = product.tickets.select_related("assigned_to", "created_by")
        qs, ctx = apply_ticket_filters(request, qs)
        qs = sort_tickets(request, qs, default=("-priority", "-created_at"))

        columns = [
            {"key": v, "label": label, "tickets": list(qs.filter(status=v))}
            for v, label in Ticket.Status.choices
        ]
        total = sum(len(c["tickets"]) for c in columns)

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_product_kanban_columns.html",
                          {"columns": columns, "total": total, "product": product})

        return render(request, "products/product_ticket_kanban.html", {
            **ctx,
            "product": product,
            "columns": columns,
            "members": product_users(product, request.company),
            "total": total,
        })


class ProductTicketCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
        from apps.tickets.forms import TicketCreateForm
        form = TicketCreateForm(company=request.company, product=product, user=request.user, initial={"product": product})
        return render(request, "products/product_ticket_form.html", {"form": form, "product": product})

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
        from apps.tickets.forms import TicketCreateForm
        form = TicketCreateForm(request.POST, company=request.company, product=product, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = request.company
            ticket.created_by = request.user
            ticket.product = product
            ticket.source = "manual"
            ticket.save()
            ticket.set_assignees(form.cleaned_data["assignees"])
            notify_ticket_created(ticket)
            log_activity(
                request.company, "ticket_created",
                f"Ticket #{ticket.pk} created",
                description=ticket.title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": product.pk},
            )
            messages.success(request, f"Ticket #{ticket.pk} created.")
            return redirect("products:product_ticket_detail", pk=product.pk, ticket_pk=ticket.pk)
        return render(request, "products/product_ticket_form.html", {"form": form, "product": product})


class ProductTicketBulkDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        from apps.tickets.models import Ticket
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        ticket_ids = request.POST.getlist("ticket_ids[]")
        if not ticket_ids:
            return JsonResponse({"error": "No tickets selected."}, status=400)
        deleted = 0
        for tid in ticket_ids:
            try:
                ticket = Ticket.objects.get(pk=tid, company=request.company, product=product)
            except (Ticket.DoesNotExist, ValueError):
                continue
            if request.company_role not in ("owner", "admin") and ticket.created_by != request.user:
                continue
            ticket_id = ticket.pk
            title = ticket.title
            ticket.delete()
            log_activity(
                request.company, "ticket_deleted",
                f"Ticket #{ticket_id} deleted",
                description=title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket_id,
                metadata={"product_id": product.pk},
            )
            deleted += 1
        return JsonResponse({"deleted": deleted})


class ProductTicketDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk, ticket_pk):
        from apps.tickets.forms import TicketCommentForm
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        _attach_product_counts(product)
        ticket = get_object_or_404(
            product.tickets.select_related("assigned_to", "created_by", "linked_error_group"),
            pk=ticket_pk,
        )
        comments = ticket.comments.select_related("author").all()
        members = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.filter(
            memberships__company=request.company
        ).order_by("username")
        from apps.products.access import product_users
        members = product_users(product, request.company)
        return render(request, "products/product_ticket_detail.html", {
            "product": product, "ticket": ticket, "comments": comments,
            "comment_form": TicketCommentForm(), "members": members,
            "assignee_selected_ids": [str(pk) for pk in ticket.assignees.values_list("pk", flat=True)],
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
            log_activity(
                request.company, "access_granted",
                f"{target_user.username} granted access to {product.name}",
                actor=request.user,
                target_content_type="product_access",
                target_object_id=obj.pk,
                metadata={"product_id": product.pk, "user_id": target_user.pk},
            )
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

        from django.contrib.auth import get_user_model
        user_pk = int(user_pk)
        target_user = get_object_or_404(get_user_model(), pk=user_pk)
        ProductAccess.objects.filter(
            product=product, user_id=user_pk, company=request.company
        ).delete()
        log_activity(
            request.company, "access_revoked",
            f"{target_user.username} access to {product.name} removed",
            actor=request.user,
            target_content_type="product_access",
            target_object_id=None,
            metadata={"product_id": product.pk, "user_id": user_pk},
        )
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


class ProductMilestoneAddView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)

        title = request.POST.get("title", "").strip()
        target_date_str = request.POST.get("target_date", "")
        order = request.POST.get("order", "1")

        if title and target_date_str:
            try:
                from datetime import datetime
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                order_num = int(order)
            except ValueError:
                target_date = timezone.localdate()
                order_num = 1

            from apps.products.models import ProductMilestone
            ProductMilestone.objects.create(
                company=request.company,
                product=product,
                title=title,
                target_date=target_date,
                order=order_num,
                status=ProductMilestone.Status.UPCOMING,
            )
            messages.success(request, f"Milestone '{title}' added to flowchart.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_milestone_tree.html", {
                "product": product,
                "milestones": product.milestones.all(),
            })
        return redirect("products:product_detail", pk=product.pk)


class ProductMilestoneToggleView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        from apps.products.models import ProductMilestone
        milestone = get_object_or_404(ProductMilestone, pk=pk, company=request.company)
        require_product_access(request, milestone.product)

        if milestone.status == ProductMilestone.Status.UPCOMING:
            milestone.status = ProductMilestone.Status.IN_PROGRESS
        elif milestone.status == ProductMilestone.Status.IN_PROGRESS:
            milestone.status = ProductMilestone.Status.COMPLETED
            milestone.completed_at = timezone.now()
        elif milestone.status == ProductMilestone.Status.OVERDUE:
            milestone.status = ProductMilestone.Status.COMPLETED
            milestone.completed_at = timezone.now()
        else:
            milestone.status = ProductMilestone.Status.UPCOMING
            milestone.completed_at = None

        milestone.save()

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_milestone_tree.html", {
                "product": milestone.product,
                "milestones": milestone.product.milestones.all(),
            })
        return redirect("products:product_detail", pk=milestone.product.pk)


class ProductMilestoneDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        from apps.products.models import ProductMilestone
        milestone = get_object_or_404(ProductMilestone, pk=pk, company=request.company)
        require_product_access(request, milestone.product)
        product = milestone.product
        milestone.delete()

        if request.headers.get("HX-Request") == "true":
            return render(request, "products/partials/_milestone_tree.html", {
                "product": product,
                "milestones": product.milestones.all(),
            })
        return redirect("products:product_detail", pk=product.pk)

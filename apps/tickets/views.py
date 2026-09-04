from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.products.access import (
    accessible_products,
    accessible_tickets,
    require_ticket_access,
    user_has_product_access,
)
from apps.products.models import Product
from apps.products.webhook import notify_ticket_assigned, notify_ticket_created, notify_ticket_status_changed
from apps.tickets.forms import TicketCommentForm, TicketCreateForm, TicketDeadlineForm, TicketEditForm
from apps.tickets.models import Ticket, TicketComment

User = get_user_model()


def _ticket_redirect(ticket):
    """Return (url_name, kwargs) pointing to the right detail page."""
    if ticket.product_id:
        return "products:product_ticket_detail", {"pk": ticket.product_id, "ticket_pk": ticket.pk}
    return "tickets:ticket_detail", {"pk": ticket.pk}


SORT_MAP = {
    "created": "created_at",
    "-created": "-created_at",
    "updated": "updated_at",
    "-updated": "-updated_at",
    "priority": "priority",
    "-priority": "-priority",
    "status": "status",
    "-status": "-status",
    "title": "title",
    "-title": "-title",
}

# The filters shared by the ticket kanban and list views, so both boards
# expose the same controls. Kanban additionally groups by status (columns);
# the List view adds a `status` dropdown on top of this.
TICKET_FILTER_KEYS = ("q", "type", "priority", "product", "assigned", "overdue", "sort")


def apply_ticket_filters(request, qs):
    """Apply the shared ticket filter querystring to ``qs``.

    Returns ``(qs, ctx)`` where ``ctx`` holds the ``current_*`` values used to
    re-render the filter bar. Does not apply ``sort`` (see ``sort_tickets``).
    """
    ctx = {}

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(title__icontains=search)
    ctx["search"] = search

    ticket_type = request.GET.get("type")
    if ticket_type:
        qs = qs.filter(ticket_type=ticket_type)
    ctx["current_type"] = ticket_type

    priority = request.GET.get("priority")
    if priority:
        qs = qs.filter(priority=priority)
    ctx["current_priority"] = priority

    product_id = request.GET.get("product")
    if product_id:
        qs = qs.filter(product_id=product_id)
    ctx["current_product"] = product_id

    assigned = request.GET.get("assigned")
    if assigned == "me":
        qs = qs.filter(assignees=request.user)
    elif assigned == "unassigned":
        qs = qs.filter(assignees__isnull=True)
    elif assigned:
        qs = qs.filter(assignees__id=assigned).distinct()
    ctx["current_assigned"] = assigned

    overdue = request.GET.get("overdue")
    if overdue:
        qs = qs.filter(
            deadline__isnull=False,
            deadline__lt=timezone.now(),
        ).exclude(status__in=["resolved", "closed"])
    ctx["current_overdue"] = overdue

    ctx["current_sort"] = request.GET.get("sort", "")
    return qs, ctx


def sort_tickets(request, qs, default):
    """Order ``qs`` by the ``sort`` querystring, falling back to ``default``
    (a tuple of field names) when it is missing or unrecognised."""
    sort = request.GET.get("sort", "")
    if sort in SORT_MAP:
        return qs.order_by(SORT_MAP[sort])
    return qs.order_by(*default)


class TicketListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = accessible_tickets(request.user, request.company).select_related("product", "assigned_to", "created_by")
        qs, ctx = apply_ticket_filters(request, qs)

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        qs = sort_tickets(request, qs, default=("-created_at",))

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_list_results.html", {"page": page})

        members = User.objects.filter(memberships__company=request.company).order_by("username")
        products = accessible_products(request.user, request.company).order_by("name")
        return render(request, "tickets/ticket_list.html", {
            **ctx,
            "page": page,
            "members": members,
            "products": products,
            "current_status": status,
            "status_choices": Ticket.Status.choices,
        })


class TicketKanbanView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = accessible_tickets(request.user, request.company).select_related("product", "assigned_to", "created_by")
        qs, ctx = apply_ticket_filters(request, qs)
        qs = sort_tickets(request, qs, default=("-priority", "-created_at"))

        columns = [
            {"key": v, "label": label, "tickets": list(qs.filter(status=v))}
            for v, label in Ticket.Status.choices
        ]
        total = sum(len(c["tickets"]) for c in columns)

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_kanban_columns.html", {"columns": columns, "total": total})

        members = User.objects.filter(memberships__company=request.company).order_by("username")
        products = accessible_products(request.user, request.company).order_by("name")
        return render(request, "tickets/ticket_kanban.html", {
            **ctx,
            "columns": columns,
            "members": members,
            "products": products,
            "total": total,
        })


class TicketCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = TicketCreateForm(company=request.company, user=request.user)
        return render(request, "tickets/ticket_form.html", {"form": form})

    def post(self, request):
        product = None
        product_id = request.POST.get("product")
        if product_id:
            from apps.products.models import Product
            product = Product.objects.filter(pk=product_id, company=request.company).first()
            if product and not user_has_product_access(request.user, request.company, product):
                product = None
        form = TicketCreateForm(request.POST, company=request.company, product=product, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = request.company
            ticket.created_by = request.user
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
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, f"Ticket #{ticket.pk} created.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
        return render(request, "tickets/ticket_form.html", {"form": form})


class TicketEditView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        form = TicketEditForm(instance=ticket)
        assignee_selected_ids = [str(a.pk) for a in ticket.assignees.all()]
        return render(request, "tickets/ticket_form.html", {
            "form": form,
            "ticket": ticket,
            "editing": True,
            "assignee_selected_ids": assignee_selected_ids,
        })

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        form = TicketEditForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save()
            ticket.set_assignees(form.cleaned_data["assignees"])
            log_activity(
                request.company, "ticket_updated",
                f"Ticket #{ticket.pk} updated",
                description=ticket.title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, f"Ticket #{ticket.pk} updated.")
            url_name, kwargs = _ticket_redirect(ticket)
            return redirect(url_name, **kwargs)
        assignee_selected_ids = request.POST.getlist("assignees")
        return render(request, "tickets/ticket_form.html", {
            "form": form,
            "ticket": ticket,
            "editing": True,
            "assignee_selected_ids": assignee_selected_ids,
        })


class TicketDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        ticket = get_object_or_404(
            Ticket.objects.select_related("product", "assigned_to", "created_by", "linked_error_group"),
            pk=pk,
            company=request.company,
        )
        require_ticket_access(request, ticket)
        comments = ticket.comments.select_related("author").all()
        comment_form = TicketCommentForm()

        members = User.objects.filter(
            memberships__company=request.company
        ).order_by("username")
        if ticket.product:
            from apps.products.access import product_users
            members = product_users(ticket.product, request.company)

        return render(request, "tickets/ticket_detail.html", {
            "ticket": ticket,
            "comments": comments,
            "comment_form": comment_form,
            "members": members,
            "assignee_selected_ids": [str(pk) for pk in ticket.assignees.values_list("pk", flat=True)],
            "status_choices": Ticket.Status.choices,
            "priority_choices": Ticket.Priority.choices,
        })


class TicketPriorityView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        new_priority = request.POST.get("priority")
        if new_priority in dict(Ticket.Priority.choices):
            old_priority = ticket.get_priority_display()
            ticket.priority = new_priority
            ticket.save(update_fields=["priority", "updated_at"])
            log_activity(
                request.company, "ticket_priority_changed",
                f"Ticket #{ticket.pk} priority changed to {ticket.get_priority_display()}",
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id, "from": old_priority, "to": ticket.get_priority_display()},
            )
            messages.success(request, f"Priority updated to {ticket.get_priority_display()}.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_priority.html", {
                "ticket": ticket,
                "priority_choices": Ticket.Priority.choices,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketStatusView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        new_status = request.POST.get("status")

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if not ticket.can_transition_to(new_status):
            msg = (
                f"'{new_status}' is not a valid status."
            )
            if is_ajax:
                return JsonResponse({"ok": False, "error": msg}, status=400)
            messages.error(request, msg)
        else:
            old_value = ticket.status
            old_display = ticket.get_status_display()
            ticket.transition_to(new_status, actor=request.user)
            notify_ticket_status_changed(ticket, old_display)
            log_activity(
                request.company, "ticket_status_changed",
                f"Ticket #{ticket.pk} status changed",
                description=f"{old_display} → {ticket.get_status_display()}",
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id, "from": old_value, "to": ticket.status},
            )
            if is_ajax:
                return JsonResponse({"ok": True, "status": ticket.status})
            messages.success(request, f"Status changed to '{ticket.get_status_display()}'.")

        if request.headers.get("HX-Request") == "true":
            members = User.objects.filter(
                memberships__company=request.company
            ).order_by("username")
            return render(request, "tickets/partials/_ticket_status.html", {
                "ticket": ticket,
                "status_choices": Ticket.Status.choices,
                "members": members,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketAssignView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        assignee_ids = request.POST.getlist("assignees")

        old_assignees = set(ticket.assignees.values_list("pk", flat=True))

        if assignee_ids:
            assignees = User.objects.filter(
                pk__in=assignee_ids,
                memberships__company=request.company,
            )
            ticket.set_assignees(assignees)
            if ticket.status == "open":
                ticket.status = "assigned"
                ticket.save(update_fields=["status", "updated_at"])
        else:
            ticket.set_assignees([])
            if ticket.status == "assigned":
                ticket.status = "open"
                ticket.save(update_fields=["status", "updated_at"])

        new_assignees = set(ticket.assignees.values_list("pk", flat=True))
        names = ", ".join(
            ticket.assignees.order_by("username").values_list("username", flat=True)
        ) or "nobody"
        notify_ticket_assigned(ticket)
        log_activity(
            request.company, "ticket_assigned",
            f"Ticket #{ticket.pk} assigned",
            description=f"Assigned to {names}",
            actor=request.user,
            target_content_type="ticket",
            target_object_id=ticket.pk,
            metadata={
                "product_id": ticket.product_id,
                "assigned_to": ",".join(map(str, sorted(new_assignees))),
                "from": ",".join(map(str, sorted(old_assignees))),
                "to": ",".join(map(str, sorted(new_assignees))),
            },
        )
        messages.success(request, f"Ticket assigned to {names}.")

        if request.headers.get("HX-Request") == "true":
            members = User.objects.filter(
                memberships__company=request.company
            ).order_by("username")
            if ticket.product:
                from apps.products.access import product_users
                members = product_users(ticket.product, request.company)
            return render(request, "tickets/partials/_ticket_assignee.html", {
                "ticket": ticket,
                "members": members,
                "assignee_selected_ids": [str(pk) for pk in ticket.assignees.values_list("pk", flat=True)],
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketCommentView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        form = TicketCommentForm(request.POST)

        if form.is_valid():
            TicketComment.objects.create(
                ticket=ticket,
                company=request.company,
                author=request.user,
                body=form.cleaned_data["body"],
            )
            log_activity(
                request.company, "ticket_commented",
                f"Comment on ticket #{ticket.pk}",
                description=form.cleaned_data["body"][:200],
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, "Comment added.")

        if request.headers.get("HX-Request") == "true":
            comments = ticket.comments.select_related("author").all()
            return render(request, "tickets/partials/_comment_list.html", {
                "comments": comments,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketDeadlineView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        form = TicketDeadlineForm(request.POST)

        if form.is_valid():
            old_deadline = ticket.deadline
            ticket.deadline = form.cleaned_data["deadline"]
            ticket.save(update_fields=["deadline", "updated_at"])
            log_activity(
                request.company, "ticket_deadline_changed",
                f"Ticket #{ticket.pk} deadline changed",
                description=(
                    f"from {old_deadline:%Y-%m-%d %H:%M} to {ticket.deadline:%Y-%m-%d %H:%M}"
                    if old_deadline and ticket.deadline
                    else f"{ticket.deadline:%Y-%m-%d %H:%M}" if ticket.deadline else "Deadline cleared"
                ),
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={
                    "product_id": ticket.product_id,
                    "from": old_deadline.isoformat() if old_deadline else None,
                    "to": ticket.deadline.isoformat() if ticket.deadline else None,
                },
            )
            messages.success(request, "Deadline updated.")

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_deadline.html", {
                "ticket": ticket,
                "deadline_error": form.errors.get("deadline"),
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)


class TicketDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        if request.company_role not in ("owner", "admin") and ticket.created_by != request.user:
            return HttpResponseForbidden("You can only delete tickets you created.")
        ticket_id = ticket.pk
        product_id = ticket.product_id
        title = ticket.title
        ticket.delete()
        log_activity(
            request.company, "ticket_deleted",
            f"Ticket #{ticket_id} deleted",
            description=title,
            actor=request.user,
            target_content_type="ticket",
            target_object_id=ticket_id,
            metadata={"product_id": product_id},
        )
        messages.success(request, f"Ticket #{ticket_id} deleted.")

        if product_id:
            return redirect("products:product_board", pk=product_id)
        return redirect("tickets:ticket_board")


class TicketBulkDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request):
        ticket_ids = request.POST.getlist("ticket_ids[]")
        if not ticket_ids:
            return JsonResponse({"error": "No tickets selected."}, status=400)
        deleted = 0
        for tid in ticket_ids:
            try:
                ticket = Ticket.objects.get(pk=tid, company=request.company)
            except (Ticket.DoesNotExist, ValueError):
                continue
            if ticket.product_id and not user_has_product_access(
                request.user, request.company, ticket.product
            ):
                continue
            if request.company_role not in ("owner", "admin") and ticket.created_by != request.user:
                continue
            ticket_id = ticket.pk
            product_id = ticket.product_id
            title = ticket.title
            ticket.delete()
            log_activity(
                request.company, "ticket_deleted",
                f"Ticket #{ticket_id} deleted",
                description=title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket_id,
                metadata={"product_id": product_id},
            )
            deleted += 1
        return JsonResponse({"deleted": deleted})

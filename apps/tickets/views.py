from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
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


class TicketListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = Ticket.objects.filter(company=request.company).select_related("product", "assigned_to", "created_by")

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        ticket_type = request.GET.get("type")
        if ticket_type:
            qs = qs.filter(ticket_type=ticket_type)

        priority = request.GET.get("priority")
        if priority:
            qs = qs.filter(priority=priority)

        product_id = request.GET.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)

        assigned = request.GET.get("assigned")
        if assigned == "me":
            qs = qs.filter(assignees=request.user)
        elif assigned == "unassigned":
            qs = qs.filter(assignees__isnull=True)
        elif assigned:
            qs = qs.filter(assignees__id=assigned)

        overdue = request.GET.get("overdue")
        if overdue:
            qs = qs.filter(
                deadline__isnull=False,
                deadline__lt=timezone.now(),
            ).exclude(status__in=["resolved", "closed"])

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        sort = request.GET.get("sort", "-created")
        order = SORT_MAP.get(sort, "-created_at")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        members = User.objects.filter(
            memberships__company=request.company
        ).order_by("username")
        products = Product.objects.filter(company=request.company).order_by("name")

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_list_body.html", {
                "page": page,
            })

        return render(request, "tickets/ticket_list.html", {
            "page": page,
            "members": members,
            "products": products,
            "current_status": status,
            "current_type": ticket_type,
            "current_priority": priority,
            "current_assigned": assigned,
            "current_overdue": overdue,
            "current_product": product_id,
            "search": search,
            "current_sort": sort,
            "status_choices": Ticket.Status.choices,
        })


class TicketKanbanView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = Ticket.objects.filter(company=request.company).select_related("product", "assigned_to", "created_by")

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(title__icontains=search)

        ticket_type = request.GET.get("type")
        if ticket_type:
            qs = qs.filter(ticket_type=ticket_type)

        priority = request.GET.get("priority")
        if priority:
            qs = qs.filter(priority=priority)

        product_id = request.GET.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)

        assigned = request.GET.get("assigned")
        if assigned == "me":
            qs = qs.filter(assignees=request.user)
        elif assigned == "unassigned":
            qs = qs.filter(assignees__isnull=True)
        elif assigned:
            qs = qs.filter(assignees__id=assigned)

        overdue = request.GET.get("overdue")
        if overdue:
            qs = qs.filter(
                deadline__isnull=False,
                deadline__lt=timezone.now(),
            ).exclude(status__in=["resolved", "closed"])

        columns = []
        for status_val, status_label in Ticket.Status.choices:
            col_qs = qs.filter(status=status_val).order_by("-priority", "-created_at")
            columns.append({"key": status_val, "label": status_label, "tickets": col_qs})

        members = User.objects.filter(
            memberships__company=request.company
        ).order_by("username")
        products = Product.objects.filter(company=request.company).order_by("name")

        return render(request, "tickets/ticket_kanban.html", {
            "columns": columns,
            "members": members,
            "products": products,
            "search": search,
            "current_type": ticket_type,
            "current_priority": priority,
            "current_product": product_id,
            "current_assigned": assigned,
            "current_overdue": overdue,
            "total": qs.count(),
            "status_choices": Ticket.Status.choices,
        })


class TicketCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = TicketCreateForm(company=request.company)
        return render(request, "tickets/ticket_form.html", {"form": form})

    def post(self, request):
        form = TicketCreateForm(request.POST, company=request.company)
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
        comments = ticket.comments.select_related("author").all()
        comment_form = TicketCommentForm()

        members = User.objects.filter(
            memberships__company=request.company
        ).order_by("username")

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_detail_content.html", {
                "ticket": ticket,
                "comments": comments,
                "comment_form": comment_form,
                "members": members,
            })

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


class TicketDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
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

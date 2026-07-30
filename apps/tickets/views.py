from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.tickets.forms import TicketCommentForm, TicketCreateForm, TicketEditForm
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

        assigned = request.GET.get("assigned")
        if assigned == "me":
            qs = qs.filter(assigned_to=request.user)
        elif assigned == "unassigned":
            qs = qs.filter(assigned_to__isnull=True)

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

        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_list_body.html", {
                "page": page,
            })

        return render(request, "tickets/ticket_list.html", {
            "page": page,
            "members": members,
            "current_status": status,
            "current_type": ticket_type,
            "current_priority": priority,
            "current_assigned": assigned,
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

        columns = []
        for status_val, status_label in Ticket.Status.choices:
            col_qs = qs.filter(status=status_val).order_by("-priority", "-created_at")
            columns.append({"key": status_val, "label": status_label, "tickets": col_qs})

        members = User.objects.filter(
            memberships__company=request.company
        ).order_by("username")

        return render(request, "tickets/ticket_kanban.html", {
            "columns": columns,
            "members": members,
            "search": search,
            "current_type": ticket_type,
            "current_priority": priority,
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
            messages.success(request, f"Ticket #{ticket.pk} created.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
        return render(request, "tickets/ticket_form.html", {"form": form})


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
            "status_choices": Ticket.Status.choices,
        })


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
            ticket.transition_to(new_status)
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
        user_id = request.POST.get("assigned_to")

        if user_id:
            assignee = get_object_or_404(User, pk=user_id, memberships__company=request.company)
            ticket.assigned_to = assignee
            if ticket.status == "open":
                ticket.status = "assigned"
        else:
            ticket.assigned_to = None
            if ticket.status == "assigned":
                ticket.status = "open"

        ticket.save(update_fields=["assigned_to", "status", "updated_at"])
        messages.success(request, f"Ticket assigned to {ticket.assigned_to or 'nobody'}.")

        if request.headers.get("HX-Request") == "true":
            members = User.objects.filter(
                memberships__company=request.company
            ).order_by("username")
            return render(request, "tickets/partials/_ticket_assignee.html", {
                "ticket": ticket,
                "members": members,
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
            messages.success(request, "Comment added.")

        if request.headers.get("HX-Request") == "true":
            comments = ticket.comments.select_related("author").all()
            return render(request, "tickets/partials/_comment_list.html", {
                "comments": comments,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)

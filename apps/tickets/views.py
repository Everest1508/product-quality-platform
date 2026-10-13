from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.products.access import require_ticket_access
from apps.notifications import service
from apps.notifications.models import Notification
from apps.products.webhook import notify_ticket_assigned, notify_ticket_created
from apps.tickets.forms import error_summary, TicketCommentForm, TicketCreateForm, TicketDeadlineForm, TicketEditForm
from apps.tickets import mentions
from apps.uiapi.shell import render_shell
from apps.tickets import service as ticket_service
from apps.tickets.models import Ticket, TicketComment
from apps.core.timefmt import t12

User = get_user_model()


def _ticket_redirect(ticket):
    """Return (url_name, kwargs) pointing to the right detail page."""
    if ticket.product_id:
        return "products:product_ticket_detail", {"pk": ticket.product_id, "ticket_pk": ticket.pk}
    return "tickets:ticket_detail", {"pk": ticket.pk}


class TicketListView(CompanyMemberRequiredMixin, View):
    """The list, served by the React shell (data from /ui-api/v1/tickets/)."""

    def get(self, request):
        return render_shell(request)


class TicketKanbanView(CompanyMemberRequiredMixin, View):
    """The board, served by the React shell (data from /ui-api/v1/tickets/?view=board)."""

    def get(self, request):
        return render_shell(request)


class TicketCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = TicketCreateForm(company=request.company, user=request.user)
        return render(request, "tickets/ticket_form.html", {"form": form})

    def post(self, request):
        # The page offers every member as an assignee whatever the product, so the form must too;
        # people without access to the chosen product are dropped below, with a warning.
        form = TicketCreateForm(request.POST, company=request.company, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.company = request.company
            ticket.created_by = request.user
            ticket.source = "manual"
            ticket.save()
            assignees = list(form.cleaned_data["assignees"])
            if ticket.product_id:
                from apps.products.access import product_users
                allowed = set(product_users(ticket.product, request.company).values_list("pk", flat=True))
                skipped = [u for u in assignees if u.pk not in allowed]
                assignees = [u for u in assignees if u.pk in allowed]
                if skipped:
                    names = ", ".join(u.get_full_name() or u.username for u in skipped)
                    messages.warning(request, f"Not assigned (no access to {ticket.product.name}): {names}.")
            ticket.set_assignees(assignees, actor=request.user)
            notify_ticket_created(ticket)
            log_activity(
                request.company, "ticket_created",
                f"Ticket {ticket.key} created",
                description=ticket.title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, f"Ticket {ticket.key} created.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
        messages.error(request, error_summary(form))
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
            ticket.set_assignees(form.cleaned_data["assignees"], actor=request.user)
            log_activity(
                request.company, "ticket_updated",
                f"Ticket {ticket.key} updated",
                description=ticket.title,
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, f"Ticket {ticket.key} updated.")
            url_name, kwargs = _ticket_redirect(ticket)
            return redirect(url_name, **kwargs)
        messages.error(request, error_summary(form))
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
        comments = ticket.comments.select_related("author").prefetch_related("mentions").all()
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
            "mention_candidates": mentions.candidates_json(ticket, request.company),
            "following": ticket.watchers.filter(pk=request.user.pk).exists(),
            "watcher_count": ticket.watchers.count(),
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
                f"Ticket {ticket.key} priority changed to {ticket.get_priority_display()}",
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id, "from": old_priority, "to": ticket.get_priority_display()},
            )
            messages.success(request, f"{ticket.key}: priority {old_priority} → {ticket.get_priority_display()}.")

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

        old_display = ticket.get_status_display()
        error = ticket_service.change_status(ticket, new_status, request.user, request.company)
        if error:
            if is_ajax:
                return JsonResponse({"ok": False, "error": error}, status=400)
            messages.error(request, error)
        else:
            if is_ajax:
                return JsonResponse({"ok": True, "status": ticket.status})
            messages.success(request, f"{ticket.key}: status {old_display} → {ticket.get_status_display()}.")

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
        message = ticket_service.assign(ticket, request.POST.getlist("assignees"), request.user, request.company)
        messages.success(request, message)

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
            body = form.cleaned_data["body"]
            comment = TicketComment.objects.create(
                ticket=ticket,
                company=request.company,
                author=request.user,
                body=body,
            )
            mentioned = mentions.resolve(body, ticket, request.company)
            comment.mentions.set(mentioned)
            self._notify(request, ticket, body, mentioned)
            log_activity(
                request.company, "ticket_commented",
                f"Comment on ticket {ticket.key}",
                description=body[:200],
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
            messages.success(request, "Comment added.")

        if request.headers.get("HX-Request") == "true":
            comments = ticket.comments.select_related("author").prefetch_related("mentions").all()
            return render(request, "tickets/partials/_comment_list.html", {
                "comments": comments,
            })
        url_name, kwargs = _ticket_redirect(ticket)
        return redirect(url_name, **kwargs)

    @staticmethod
    def _notify(request, ticket, body, mentioned):
        """Mentioned people get a mention; the assignees and the creator get a
        plain comment notice. Nobody gets both, and the author gets neither."""
        who = request.user.get_full_name() or request.user.username
        snippet = body.strip().replace("\n", " ")[:140]
        url = f"/tickets/{ticket.pk}/"
        service.notify_many(
            mentioned,
            company=request.company,
            kind=Notification.Kind.MENTION,
            title=f"{who} mentioned you on ticket {ticket.key}",
            body=snippet,
            url=url,
            actor=request.user,
        )
        already = {u.pk for u in mentioned}
        watchers = [u for u in ticket.assignees.all() if u.pk not in already]
        if ticket.created_by and ticket.created_by.pk not in already:
            watchers.append(ticket.created_by)
        # Followers too, once each: someone can be an assignee and a follower.
        seen = already | {u.pk for u in watchers}
        watchers += [u for u in ticket.watchers.all() if u.pk not in seen]
        service.notify_many(
            watchers,
            company=request.company,
            kind=Notification.Kind.COMMENT,
            title=f"{who} commented on ticket {ticket.key}",
            body=snippet,
            url=url,
            actor=request.user,
        )


class TicketFollowView(CompanyMemberRequiredMixin, View):
    """Follow or unfollow a ticket without being assigned to it."""

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk, company=request.company)
        require_ticket_access(request, ticket)
        if ticket.watchers.filter(pk=request.user.pk).exists():
            ticket.watchers.remove(request.user)
            messages.success(request, f"You unfollowed {ticket.key}.")
            log_activity(
                request.company, "ticket_unfollowed",
                f"{request.user.username} unfollowed {ticket.key}",
                description=ticket.title[:200],
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
        else:
            ticket.watchers.add(request.user)
            messages.success(request, f"You are following {ticket.key}. You will be told about comments and status changes.")
            log_activity(
                request.company, "ticket_followed",
                f"{request.user.username} is following {ticket.key}",
                description=ticket.title[:200],
                actor=request.user,
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": ticket.product_id},
            )
        if request.headers.get("HX-Request") == "true":
            return render(request, "tickets/partials/_ticket_follow.html", {
                "ticket": ticket, "following": ticket.watchers.filter(pk=request.user.pk).exists(),
                "watcher_count": ticket.watchers.count(),
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
                f"Ticket {ticket.key} deadline changed",
                description=(
                    f"from {old_deadline:%Y-%m-%d} {t12(old_deadline)} to {ticket.deadline:%Y-%m-%d} {t12(ticket.deadline)}"
                    if old_deadline and ticket.deadline
                    else f"{ticket.deadline:%Y-%m-%d} {t12(ticket.deadline)}" if ticket.deadline else "Deadline cleared"
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
            messages.success(
                request,
                f"{ticket.key}: deadline set to {ticket.deadline:%b %d, %Y} {t12(ticket.deadline)}."
                if ticket.deadline else f"{ticket.key}: deadline cleared.",
            )

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
        if not ticket_service.can_delete_ticket(request.user, request.company_role, ticket):
            return HttpResponseForbidden("You can only delete tickets you created.")
        product_id = ticket.product_id
        ticket_key = ticket_service.delete_ticket(ticket, request.user, request.company)
        messages.success(request, f"Ticket {ticket_key} deleted.")

        if product_id:
            return redirect("products:product_board", pk=product_id)
        return redirect("tickets:ticket_board")



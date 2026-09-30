from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.models import Membership
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.leave import service
from apps.leave.forms import LeavePolicyForm, LeaveRequestForm
from apps.leave.models import LeavePolicy, LeaveRequest


def is_approver(user, company):
    """Company-level approver: the flag, or an owner/admin who already has
    the final say over the workspace."""
    membership = Membership.objects.filter(user=user, company=company).first()
    if not membership:
        return False
    return membership.is_leave_approver or membership.role in (
        Membership.Role.OWNER,
        Membership.Role.ADMIN,
    )


class LeaveApproverRequiredMixin(CompanyMemberRequiredMixin):
    """Restrict a view to leave approvers, 403 otherwise.

    The check runs *before* the view, not after: deciding a request is a
    mutation, so a rejection that happened post-hoc would be too late.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.company and not is_approver(
            request.user, request.company
        ):
            return HttpResponseForbidden("Only leave approvers can do this.")
        return super().dispatch(request, *args, **kwargs)


def _log(
    request,
    event,
    title,
    target,
    description="",
    metadata=None,
    content_type="leave_request",
):
    log_activity(
        request.company,
        event,
        title,
        description=description,
        actor=request.user,
        target_content_type=content_type,
        target_object_id=target.pk,
        metadata=metadata,
    )


def _request_context(request, extra=None):
    today = timezone.localdate()
    context = {
        "today": today,
        "can_approve": is_approver(request.user, request.company),
    }
    context.update(extra or {})
    return context


def _selected_year(request):
    try:
        return int(request.GET["year"])
    except (KeyError, TypeError, ValueError):
        return timezone.localdate().year


class MyLeaveView(CompanyMemberRequiredMixin, View):
    """Balances plus this employee's own request history."""

    template_name = "leave/my_leave.html"

    def get(self, request):
        year = _selected_year(request)

        requests = (
            LeaveRequest.objects.filter(company=request.company, user=request.user)
            .select_related("policy", "decided_by")
            .order_by("-created_at")
        )

        context = _request_context(
            request,
            {
                "balances": service.balances_for(request.company, request.user, year),
                "requests": requests,
                "year": year,
                "year_label": str(year),
            },
        )
        return render(request, self.template_name, context)


class LeaveApplyView(CompanyMemberRequiredMixin, View):
    """Apply for leave. Everyone who is a company member may apply."""

    template_name = "leave/apply.html"

    def get(self, request):
        form = LeaveRequestForm(company=request.company, user=request.user)
        context = _request_context(
            request,
            {
                "form": form,
                "balances": service.balances_for(request.company, request.user),
            },
        )
        if request.headers.get("HX-Request") == "true":
            return render(request, "leave/partials/_apply_form.html", context)
        return render(request, self.template_name, context)

    def post(self, request):
        form = LeaveRequestForm(
            request.POST, company=request.company, user=request.user
        )
        context = _request_context(
            request,
            {
                "form": form,
                "balances": service.balances_for(request.company, request.user),
            },
        )
        if request.headers.get("HX-Request") == "true":
            if not form.is_valid():
                return render(request, "leave/partials/_apply_form.html", context, status=400)
            form.save(request.user)
            context["form"] = LeaveRequestForm(company=request.company, user=request.user)
            return render(request, "leave/partials/_apply_form.html", context)

        if form.is_valid():
            leave = form.save(request.user)
            _log(
                request,
                "leave_requested",
                f"{request.user.get_full_name() or request.user.username} applied for "
                f"{leave.policy.name} leave",
                leave,
                description=f"{leave.span_label} · {leave.days_label}",
                metadata={
                    "policy": leave.policy.name,
                    "start_date": leave.start_date.isoformat(),
                    "end_date": leave.end_date.isoformat(),
                    "days": str(leave.days),
                },
            )
            messages.success(request, "Leave request submitted for approval.")
            return redirect("leave:my_leave")

        return render(request, self.template_name, context)


class LeaveCancelView(CompanyMemberRequiredMixin, View):
    """Withdraw your own pending request."""

    def post(self, request, pk):
        leave = get_object_or_404(
            LeaveRequest, pk=pk, company=request.company, user=request.user
        )
        if not leave.is_pending:
            messages.error(request, "Only a pending request can be withdrawn.")
            return redirect("leave:my_leave")

        leave.status = LeaveRequest.Status.CANCELLED
        leave.decided_at = timezone.now()
        leave.decided_by = request.user
        leave.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
        _log(
            request,
            "leave_cancelled",
            f"{leave.user.get_full_name() or leave.user.username} withdrew a "
            f"{leave.policy.name} leave request",
            leave,
            description=leave.span_label,
        )
        messages.success(request, "Leave request withdrawn.")
        return redirect("leave:my_leave")


class LeaveQueueView(LeaveApproverRequiredMixin, View):
    """Approvers: every pending request in the company."""

    template_name = "leave/approvals.html"

    def get(self, request):
        status = request.GET.get("status", LeaveRequest.Status.PENDING)
        if status not in dict(LeaveRequest.Status.choices):
            status = LeaveRequest.Status.PENDING

        requests = (
            LeaveRequest.objects.filter(company=request.company, status=status)
            .select_related("user", "policy", "decided_by")
            .order_by("start_date")
        )

        counts = {
            row["status"]: row["n"]
            for row in LeaveRequest.objects.filter(company=request.company)
            .values("status")
            .annotate(n=Count("id"))
        }
        tabs = [
            {
                "value": value,
                "label": label,
                "count": counts.get(value, 0),
                "is_active": value == status,
            }
            for value, label in LeaveRequest.Status.choices
        ]

        context = _request_context(
            request,
            {
                "requests": requests,
                "status": status,
                "tabs": tabs,
            },
        )
        if request.headers.get("HX-Request") == "true":
            return render(request, "leave/partials/_approval_list.html", context)
        return render(request, self.template_name, context)


class LeaveDecisionView(LeaveApproverRequiredMixin, View):
    """Approve or reject a pending request."""

    ACTIONS = {
        "approve": LeaveRequest.Status.APPROVED,
        "reject": LeaveRequest.Status.REJECTED,
    }

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            messages.error(request, "Unknown action.")
            return redirect("leave:approvals")

        leave = get_object_or_404(LeaveRequest, pk=pk, company=request.company)
        if not leave.is_pending:
            messages.error(request, "That request has already been decided.")
            return redirect("leave:approvals")

        leave.status = self.ACTIONS[action]
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.decision_note = request.POST.get("note", "").strip()
        leave.save(
            update_fields=[
                "status",
                "decided_by",
                "decided_at",
                "decision_note",
                "updated_at",
            ]
        )

        who = leave.user.get_full_name() or leave.user.username
        _log(
            request,
            "leave_approved" if action == "approve" else "leave_rejected",
            f"{leave.policy.name} leave for {who} {leave.status}",
            leave,
            description=leave.span_label,
            metadata={"decided_by": request.user.username, "status": leave.status},
        )
        verb = "approved" if action == "approve" else "rejected"
        messages.success(request, f"Leave for {who} {verb}.")
        return redirect("leave:approvals")


class LeavePolicyListView(CompanyAdminRequiredMixin, View):
    """Admin: the per-type allowance and spell cap."""

    template_name = "leave/policies.html"

    def get(self, request):
        context = _request_context(
            request,
            {
                "policies": service.policies_for(request.company),
                "model": LeavePolicy,
            },
        )
        if request.headers.get("HX-Request") == "true":
            return render(request, "leave/partials/_policy_table.html", context)
        return render(request, self.template_name, context)


class LeavePolicyCreateView(CompanyAdminRequiredMixin, View):
    """Admin: add a leave type.

    The policy screen's empty state has always told the admin to "add a leave
    type", but until now there was no route that could do it -- a company
    whose policies were all removed could never get one back.
    """

    def post(self, request):
        form = LeavePolicyForm(request.POST)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.company = request.company
            policy.save()
            _log(
                request,
                "leave_policy_created",
                f"{policy.name} leave policy created",
                policy,
                description=policy.annual_limit_label,
                content_type="leave_policy",
                metadata={
                    "policy": policy.name,
                    "max_days_per_year": str(policy.max_days_per_year),
                    "max_consecutive_days": str(policy.max_consecutive_days),
                },
            )
            messages.success(request, f"{policy.name} leave type added.")
        else:
            for error in form.non_field_errors() or []:
                messages.error(request, error)
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

        return redirect("leave:policies")


class LeavePolicyUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        policy = get_object_or_404(LeavePolicy, pk=pk, company=request.company)
        form = LeavePolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            _log(
                request,
                "leave_policy_updated",
                f"{policy.name} leave policy updated",
                policy,
                description=f"{policy.annual_limit_label} · {policy.consecutive_limit_label}",
                content_type="leave_policy",
                metadata={
                    "policy": policy.name,
                    "max_days_per_year": str(policy.max_days_per_year),
                    "max_consecutive_days": str(policy.max_consecutive_days),
                },
            )
            messages.success(request, f"{policy.name} leave policy updated.")
        else:
            for error in form.non_field_errors() or []:
                messages.error(request, error)

        return redirect("leave:policies")
import datetime
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.models import Membership
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.leave import service
from apps.leave.forms import LeaveDecisionForm, LeavePolicyForm, LeaveRequestForm
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


def _report_errors(request, form):
    """Turn every form error into a toast.

    Both policy views redirect back to the list on failure, so a message is the
    only channel an error has -- and an error left out of it is an error the
    person who typed it never sees. The create view reported field errors and
    the update view did not, which meant a rejected paid spell cap was visible
    when adding a type and invisible when editing one.

    Labels come from the form rather than from `field.replace("_", " ")`, so the
    toast says "Paid days per spell" and not "max_consecutive_days".
    """
    labels = getattr(form, "fields", {})
    for field, errors in form.errors.items():
        if field == "__all__":
            for error in errors:
                messages.error(request, error)
            continue
        label = labels[field].label or field.replace("_", " ")
        for error in errors:
            messages.error(request, f"{label}: {error}")


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


class LeaveSplitPreviewView(CompanyMemberRequiredMixin, View):
    """What the posted dates would be charged as, before anything is saved.

    An applicant can no longer discover after submitting that their spell is half
    unpaid, so the apply screen has to show the split while they type. It is a
    preview, never a decision: nothing here is stored, and the numbers are
    recomputed on submit by the same `service.auto_split` that the preview used.

    Errors are rendered as an empty panel rather than as a 400. A half-typed
    range -- an end date before the start, or a weekend-only span -- is the
    normal state of the form while somebody is still filling it in, and
    decorating every keystroke with a validation error would be noise.
    """

    template_name = "leave/partials/_split_preview.html"

    def post(self, request):
        policy_id = request.POST.get("policy_id")
        start = request.POST.get("start_date")
        end = request.POST.get("end_date") or start
        half = bool(request.POST.get("is_half_day"))

        def panel(**kwargs):
            return render(request, self.template_name, kwargs)

        if not (policy_id and start):
            return panel()
        try:
            policy = LeavePolicy.objects.get(
                pk=policy_id, company=request.company
            )
        except (LeavePolicy.DoesNotExist, ValueError, TypeError):
            return panel()

        try:
            first, last = _parse_dates(start, end)
            days = Decimal("0.5") if half else service.working_days(first, last)
        except ValidationError:
            return panel()
        if days <= 0:
            return panel()  # weekend-only span: nothing to price yet

        result = service.auto_split(
            request.company, request.user, policy, first, last, days
        )
        return panel(preview=result, policy=policy, days=days)


def _parse_dates(start, end):
    """The two POSTed dates as `date` objects, or a ValidationError."""

    def one(value):
        try:
            return datetime.date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValidationError("Enter a date.")

    first = one(start)
    last = one(end)
    if last < first:
        raise ValidationError("End date is before the start date.")
    return first, last


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
                "decision_items": self._decision_items(request, requests),
            },
        )
        if request.headers.get("HX-Request") == "true":
            return render(request, "leave/partials/_approval_list.html", context)
        return render(request, self.template_name, context)

    def _decision_items(self, request, requests):
        """The approver dialog's data, as one payload for the whole page.

        Only pending requests are actionable, so only they get a payload entry.
        A single JSON blob plus one shared dialog beats a dialog per row: the
        queue can be a hundred requests long and a hundred hidden modals is a
        hundred forms for the browser to parse on every visit.
        """
        if str(LeaveRequest.Status.PENDING) != request.GET.get(
            "status", LeaveRequest.Status.PENDING
        ):
            return []
        items = []
        for leave in requests:
            preview = service.decision_preview(request.company, leave)
            items.append(
                {
                    "pk": leave.pk,
                    "who": leave.user.get_full_name() or leave.user.username,
                    "username": leave.user.username,
                    "policy": leave.policy.name,
                    "reason": leave.reason,
                    "start": leave.start_date.isoformat(),
                    "end": leave.end_date.isoformat(),
                    "span": leave.span_label,
                    "days": str(leave.days),
                    "days_label": leave.days_label,
                    "is_half_day": leave.is_half_day,
                    "paid": str(leave.split["paid"]),
                    "unpaid": str(leave.split["unpaid"]),
                    "split_label": leave.split_label,
                    "split_mode": leave.split_mode,
                    "auto_paid": str(preview["paid"]),
                    "auto_unpaid": str(preview["unpaid"]),
                    "auto_paid_label": preview["paid_label"],
                    "auto_unpaid_label": preview["unpaid_label"],
                    "reasons": preview["reasons"],
                    "approve_url": reverse(
                        "leave:decision", args=[leave.pk, "approve"]
                    ),
                    "reject_url": reverse(
                        "leave:decision", args=[leave.pk, "reject"]
                    ),
                }
            )
        return items


class LeaveDecisionView(LeaveApproverRequiredMixin, View):
    """Approve or reject a pending request.

    An approver decides three things, not one: whether it is approved, whether
    the days are paid, and (optionally) a different span than was applied for.
    All three land on the request, and the split is stored rather than left to
    be re-derived, so the payslip months later prices the same days this screen
    showed.
    """

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

        who = leave.user.get_full_name() or leave.user.username
        if action == "reject":
            # A rejection has no paid/unpaid split to record -- nobody is going
            # anywhere -- so it takes the note and nothing else. The form is
            # still validated, because a rejection carrying an unparseable date
            # is a stale dialog, and silently ignoring the typo would decide a
            # request the approver was looking at a different one.
            form = LeaveDecisionForm(request.POST, company=request.company, leave=leave)
            if not form.is_valid():
                for error in form.non_field_errors():
                    messages.error(request, error)
                return redirect("leave:approvals")
            leave.status = LeaveRequest.Status.REJECTED
            leave.decision_note = form.cleaned_data.get("note", "").strip()
            leave.decided_by = request.user
            leave.decided_at = timezone.now()
            leave.save(
                update_fields=[
                    "status",
                    "decided_by",
                    "decided_at",
                    "decision_note",
                    "updated_at",
                ]
            )
            self._log_decision(request, leave, "leave_rejected", "rejected")
            messages.success(request, f"Leave for {who} rejected.")
            return redirect("leave:approvals")

        form = LeaveDecisionForm(request.POST, company=request.company, leave=leave)
        if not form.is_valid():
            for error in form.non_field_errors():
                messages.error(request, error)
            for field, errors in form.errors.items():
                if field in ("note", "split_mode"):
                    continue
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            return redirect("leave:approvals")

        cleaned = form.cleaned_data
        leave.start_date = cleaned["start_date"]
        leave.end_date = cleaned["end_date"]
        leave.is_half_day = cleaned.get("is_half_day", False)
        leave.days = cleaned["days"]
        leave.paid_days = cleaned["paid_days"]
        leave.unpaid_days = cleaned["unpaid_days"]
        leave.split_mode = cleaned.get("split_mode") or LeaveRequest.SplitMode.AUTO
        leave.status = LeaveRequest.Status.APPROVED
        leave.decided_by = request.user
        leave.decided_at = timezone.now()
        leave.decision_note = cleaned.get("note", "").strip()
        leave.save(
            update_fields=[
                "start_date",
                "end_date",
                "is_half_day",
                "days",
                "paid_days",
                "unpaid_days",
                "split_mode",
                "status",
                "decided_by",
                "decided_at",
                "decision_note",
                "updated_at",
            ]
        )
        self._log_decision(request, leave, "leave_approved", "approved")
        summary = f"{leave.split_label} of {leave.days_label}"
        messages.success(request, f"Leave for {who} approved — {summary}.")
        return redirect("leave:approvals")

    def _log_decision(self, request, leave, event, verb):
        who = leave.user.get_full_name() or leave.user.username
        _log(
            request,
            event,
            f"{leave.policy.name} leave for {who} {leave.status}",
            leave,
            description=leave.span_label,
            metadata={
                "decided_by": request.user.username,
                "status": leave.status,
                # The split is on the audit trail, not just the row: "approved"
                # alone cannot answer what somebody was paid for.
                "paid_days": str(leave.split["paid"]),
                "unpaid_days": str(leave.split["unpaid"]),
                "split_mode": leave.split_mode,
            },
        )


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
            _report_errors(request, form)

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
            _report_errors(request, form)

        return redirect("leave:policies")
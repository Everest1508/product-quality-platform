"""Leave actions with their side effects (audit trail, notifications), shared by the JSON API.
Access checks stay with the caller."""

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Membership
from apps.dashboards.service import log_activity
from apps.leave import service
from apps.leave.models import LeavePolicy
from apps.leave.forms import LeaveDecisionForm, LeavePolicyForm, LeaveRequestForm
from apps.leave.models import LeaveRequest
from apps.notifications import service as notifications
from apps.notifications.models import Notification


def is_approver(user, company):
    """Company-level approver: the flag, or an owner/admin who already has the final say."""
    membership = Membership.objects.filter(user=user, company=company).first()
    return bool(membership and (membership.is_leave_approver or membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)))


def approvers(company):
    """Everyone who can decide leave: owners, admins and flagged approvers."""
    return [
        m.user
        for m in Membership.objects.filter(company=company)
        .filter(Q(is_leave_approver=True) | Q(role__in=[Membership.Role.OWNER, Membership.Role.ADMIN]))
        .select_related("user")
    ]


def _log(company, actor, event, title, target, description="", metadata=None, content_type="leave_request"):
    log_activity(company, event, title, description=description, actor=actor, target_content_type=content_type,
                 target_object_id=target.pk, metadata=metadata)


def _who(user):
    return user.get_full_name() or user.username


def apply_for_leave(company, user, data):
    """Returns (leave, form); leave is None when the form is invalid. Logs it and tells the approvers, with who else is off."""
    form = LeaveRequestForm(data, company=company, user=user)
    if not form.is_valid():
        return None, form
    leave = form.save(user)
    who = _who(user)
    _log(company, user, "leave_requested", f"{who} applied for {leave.policy.name} leave", leave,
         description=f"{leave.span_label} · {leave.days_label}",
         metadata={"policy": leave.policy.name, "start_date": leave.start_date.isoformat(), "end_date": leave.end_date.isoformat(), "days": str(leave.days)})
    clash = service.clash_for(company, user, leave.start_date, leave.end_date, exclude_pk=leave.pk)
    notifications.notify_many(
        approvers(company), company=company, kind=Notification.Kind.LEAVE_REQUEST, title=f"{who} asked for {leave.policy.name} leave",
        body=f"{leave.span_label} · {leave.days_label}. {service.clash_sentence(clash)}".strip(), url=reverse("leave:approvals"), actor=user,
    )
    return leave, form


def cancel_request(company, user, leave):
    """Withdraw your own pending request. Returns an error message or None."""
    if not leave.is_pending:
        return "Only a pending request can be withdrawn."
    leave.status = LeaveRequest.Status.CANCELLED
    leave.decided_at = timezone.now()
    leave.decided_by = user
    leave.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
    _log(company, user, "leave_cancelled", f"{_who(leave.user)} withdrew a {leave.policy.name} leave request", leave, description=leave.span_label)
    return None


def _decision_log(company, approver, leave, event, verb):
    notifications.notify(
        user=leave.user, company=company, kind=Notification.Kind.LEAVE_DECISION, title=f"Your {leave.policy.name} leave was {verb}",
        body=(leave.decision_note or f"{leave.span_label} · {leave.days_label}")[:200], url=reverse("leave:my_leave"), actor=approver,
    )
    _log(company, approver, event, f"{leave.policy.name} leave for {_who(leave.user)} {leave.status}", leave, description=leave.span_label,
         metadata={"decided_by": approver.username, "status": leave.status, "paid_days": str(leave.split["paid"]),
                   "unpaid_days": str(leave.split["unpaid"]), "split_mode": leave.split_mode})


def decide(company, approver, leave, action, data):
    """Approve or reject a pending request. An approver decides three things: whether it is approved, whether the days
    are paid, and optionally a different span. Returns (message, None) or (None, form_or_message_errors)."""
    if action not in ("approve", "reject"):
        return None, "Unknown action."
    if not leave.is_pending:
        return None, "That request has already been decided."
    who = _who(leave.user)
    if approver.pk == leave.user_id and any(u.pk != approver.pk for u in approvers(company)):
        return None, "This is your own request, so another approver has to decide it."
    if action == "reject":
        # A rejection only needs the note: validating dates here would leave a request whose start has passed undecidable.
        note = data.get("note")
        leave.status, leave.decision_note = LeaveRequest.Status.REJECTED, (note.strip()[:255] if isinstance(note, str) else "")
        leave.decided_by, leave.decided_at = approver, timezone.now()
        leave.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"])
        _decision_log(company, approver, leave, "leave_rejected", "rejected")
        return f"Leave for {who} rejected.", None
    form = LeaveDecisionForm(data, company=company, leave=leave)
    if not form.is_valid():
        # A rejection carrying an unparseable date is a stale dialog; say so rather than decide the wrong request.
        errors = [e for e in form.non_field_errors()]
        if action == "approve":
            for field, errs in form.errors.items():
                if field not in ("note", "split_mode", "__all__"):
                    errors += [f"{field}: {e}" for e in errs]
        return None, errors or ["Could not save that decision."]
    c = form.cleaned_data
    now = timezone.now()
    leave.start_date, leave.end_date = c["start_date"], c["end_date"]
    leave.is_half_day = c.get("is_half_day", False)
    leave.days, leave.paid_days, leave.unpaid_days = c["days"], c["paid_days"], c["unpaid_days"]
    leave.split_mode = c.get("split_mode") or LeaveRequest.SplitMode.AUTO
    leave.status, leave.decided_by, leave.decided_at = LeaveRequest.Status.APPROVED, approver, now
    leave.decision_note = c.get("note", "").strip()
    leave.save(update_fields=["start_date", "end_date", "is_half_day", "days", "paid_days", "unpaid_days", "split_mode", "status",
                              "decided_by", "decided_at", "decision_note", "updated_at"])
    _decision_log(company, approver, leave, "leave_approved", "approved")
    return f"Leave for {who} approved — {leave.split_label} of {leave.days_label}.", None


def save_policy(company, actor, data, policy=None):
    """Create (policy None) or update a leave type. Returns (policy, form); policy is None when invalid."""
    form = LeavePolicyForm(data, instance=policy)
    if form.is_valid():
        taken = LeavePolicy.objects.filter(company=company, name=form.cleaned_data["name"])
        if policy is not None:
            taken = taken.exclude(pk=policy.pk)
        if taken.exists():
            form.add_error("name", "A leave type with this name already exists.")
    if not form.is_valid():
        return None, form
    created = policy is None
    saved = form.save(commit=False)
    if created:
        saved.company = company
    saved.save()
    meta = {"policy": saved.name, "max_days_per_year": str(saved.max_days_per_year), "max_consecutive_days": str(saved.max_consecutive_days)}
    if created:
        _log(company, actor, "leave_policy_created", f"{saved.name} leave policy created", saved, description=saved.annual_limit_label, content_type="leave_policy", metadata=meta)
    else:
        _log(company, actor, "leave_policy_updated", f"{saved.name} leave policy updated", saved,
             description=f"{saved.annual_limit_label} · {saved.consecutive_limit_label}", content_type="leave_policy", metadata=meta)
    return saved, form

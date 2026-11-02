import json
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

_EVENT_PILLS = {
    # Tickets
    "ticket_created": "open",
    "auto_ticket": "open",
    "ticket_assigned": "assigned",
    "ticket_status_changed": "progress",
    "ticket_resolved": "resolved",
    "ticket_commented": "info",
    "ticket_deleted": "critical",
    # Errors
    "error_captured": "critical",
    "error_created": "critical",
    "error_status_changed": "progress",
    "error_resolved": "resolved",
    "error_ignored": "closed",
    "error_deleted": "critical",
    # Feedback
    "feedback_received": "csat",
    "survey_response": "nps",
    "survey_created": "active",
    "survey_toggled": "progress",
    "survey_deleted": "closed",
    # Security / Membership / Access
    "member_joined": "active",
    "member_removed": "closed",
    "member_role_changed": "progress",
    "api_key_created": "active",
    "api_key_revoked": "closed",
    "access_granted": "active",
    "access_revoked": "closed",
    # Products & Projects
    "product_created": "active",
    "product_updated": "progress",
    "product_deleted": "closed",
    "version_added": "active",
    "version_removed": "closed",
    "project_stage": "progress",
    "project_log": "info",
    "project_plan": "active",
    "project_team": "assigned",
    "project_crunch": "warn",
    # Automation
    "rule_created": "active",
    "rule_updated": "progress",
    "rule_deleted": "closed",
    "rule_toggled": "progress",
    # Attendance & Leave
    "attendance_checked_in": "open",
    "attendance_checked_out": "closed",
    "attendance_edited": "warn",
    "weekly_off_changed": "info",
    "leave_requested": "pending",
    "leave_approved": "approved",
    "leave_rejected": "rejected",
    "leave_cancelled": "cancelled",
    "leave_policy_updated": "active",
    # Payroll & Expenses
    "payroll_run": "approved",
    "payroll_profile_saved": "active",
    "holiday_added": "active",
    "holiday_removed": "closed",
    "expense_added": "active",
    "expense_commented": "info",
    "expense_comment_deleted": "closed",
}


@register.filter
def event_pill(event_type):
    return _EVENT_PILLS.get(event_type, "info")


@register.filter
def event_icon(event_type):
    et = str(event_type or "").lower()
    if et.startswith("ticket_") or et == "auto_ticket":
        return "ticket"
    if et.startswith("error_"):
        return "triangle-alert"
    if et.startswith("survey_") or et.startswith("feedback_"):
        return "headset"
    if et.startswith("member_") or et.startswith("access_"):
        return "users"
    if et.startswith("api_key_"):
        return "key"
    if et.startswith("product_") or et.startswith("project_") or et.startswith("version_"):
        return "package"
    if et.startswith("rule_"):
        return "sliders"
    if et.startswith("attendance_"):
        return "clock"
    if et.startswith("leave_"):
        return "calendar"
    if et.startswith("payroll_") or et.startswith("expense_"):
        return "banknote"
    return "activity"


@register.filter
def event_label(event_type):
    from apps.dashboards.models import ActivityLog
    return dict(ActivityLog.EventType.choices).get(event_type, event_type.replace("_", " ").title())


@register.filter
def event_pretty_meta(val):
    """Format metadata into a clean JSON string for the inspection disclosure."""
    if isinstance(val, dict):
        meta = val
    else:
        meta = getattr(val, "metadata", None)
    if not meta or not isinstance(meta, dict):
        return ""
    try:
        return json.dumps(meta, indent=2)
    except Exception:
        return str(meta)


@register.filter
def event_url(entry):
    if not entry:
        return ""

    from django.urls import reverse

    try:
        et = getattr(entry, "event_type", "") or ""
        ct = getattr(entry, "target_content_type", "") or ""
        oid = getattr(entry, "target_object_id", None)
        meta = getattr(entry, "metadata", {}) or {}
        pid = meta.get("product_id") if isinstance(meta, dict) else None

        # Errors
        if et.startswith("error_") or ct in ("error", "error_group"):
            if oid and et != "error_deleted":
                return reverse("errors:error_detail", kwargs={"pk": oid})
            if pid:
                return reverse("products:product_errors", kwargs={"pk": pid})
            return reverse("errors:error_list")

        # Tickets
        if et.startswith("ticket_") or et == "auto_ticket" or ct == "ticket":
            if oid and et != "ticket_deleted":
                return reverse("tickets:ticket_detail", kwargs={"pk": oid})
            return reverse("tickets:ticket_board")

        # Surveys & Feedback
        if et.startswith("survey_") or et == "feedback_received" or ct == "survey":
            if oid and et != "survey_deleted":
                return reverse("feedback:survey_detail", kwargs={"pk": oid})
            return reverse("feedback:cs_hub")

        # Products & Product-scoped items
        if et.startswith("product_") or et.startswith("version_") or et.startswith("api_key_") or et.startswith("access_") or et.startswith("rule_") or ct == "product":
            target_pk = pid or (oid if ct == "product" else None)
            if target_pk and et != "product_deleted":
                return reverse("products:product_detail", kwargs={"pk": target_pk})
            return reverse("products:project_board")

        # Team / Membership
        if et.startswith("member_") or ct == "membership":
            return reverse("accounts:team_list")

        # Payroll & Expenses
        if et.startswith("payroll_") or ct in ("payroll", "payslip"):
            return reverse("payroll:run_list")
        if et.startswith("expense_") or ct == "expense":
            return reverse("expenses:expense_list")

        # Attendance & Leave
        if et.startswith("attendance_") or ct in ("attendance", "attendancerecord"):
            return reverse("attendance:team_attendance")
        if et.startswith("leave_") or ct in ("leave", "leaverequest"):
            return reverse("leave:approvals")

        # Automation
        if et.startswith("rule_") or ct == "rule":
            return reverse("automation:rule_list")

    except Exception:
        pass

    return ""

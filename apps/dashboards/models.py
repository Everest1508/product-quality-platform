from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class ActivityLog(TenantScopedModel):
    class EventType(models.TextChoices):
        ERROR_CAPTURED = "error_captured", "Error Captured"
        ERROR_CREATED = "error_created", "Error Created"
        ERROR_RESOLVED = "error_resolved", "Error Resolved"
        ERROR_IGNORED = "error_ignored", "Error Ignored"
        ERROR_STATUS_CHANGED = "error_status_changed", "Error Status Changed"
        ERROR_DELETED = "error_deleted", "Error Deleted"
        TICKET_CREATED = "ticket_created", "Ticket Created"
        TICKET_STATUS_CHANGED = "ticket_status_changed", "Ticket Status Changed"
        TICKET_ASSIGNED = "ticket_assigned", "Ticket Assigned"
        TICKET_COMMENTED = "ticket_commented", "Ticket Commented"
        TICKET_RESOLVED = "ticket_resolved", "Ticket Resolved"
        TICKET_DELETED = "ticket_deleted", "Ticket Deleted"
        FEEDBACK_RECEIVED = "feedback_received", "Feedback Received"
        SURVEY_RESPONSE = "survey_response", "Survey Response"
        SURVEY_CREATED = "survey_created", "Survey Created"
        SURVEY_TOGGLED = "survey_toggled", "Survey Status Changed"
        SURVEY_DELETED = "survey_deleted", "Survey Deleted"
        MEMBER_JOINED = "member_joined", "Member Joined"
        MEMBER_REMOVED = "member_removed", "Member Removed"
        MEMBER_ROLE_CHANGED = "member_role_changed", "Member Role Changed"
        PRODUCT_CREATED = "product_created", "Product Created"
        PRODUCT_UPDATED = "product_updated", "Product Updated"
        PRODUCT_DELETED = "product_deleted", "Product Deleted"
        API_KEY_CREATED = "api_key_created", "API Key Created"
        API_KEY_REVOKED = "api_key_revoked", "API Key Revoked"
        VERSION_ADDED = "version_added", "Version Added"
        VERSION_REMOVED = "version_removed", "Version Removed"
        ACCESS_GRANTED = "access_granted", "Access Granted"
        ACCESS_REVOKED = "access_revoked", "Access Revoked"
        RULE_CREATED = "rule_created", "Rule Created"
        RULE_UPDATED = "rule_updated", "Rule Updated"
        RULE_DELETED = "rule_deleted", "Rule Deleted"
        RULE_TOGGLED = "rule_toggled", "Rule Toggled"
        AUTO_TICKET = "auto_ticket", "Auto Ticket Created"
        ATTENDANCE_CHECKED_IN = "attendance_checked_in", "Attendance Checked In"
        ATTENDANCE_CHECKED_OUT = "attendance_checked_out", "Attendance Checked Out"
        ATTENDANCE_EDITED = "attendance_edited", "Attendance Edited"
        LEAVE_REQUESTED = "leave_requested", "Leave Requested"
        LEAVE_APPROVED = "leave_approved", "Leave Approved"
        LEAVE_REJECTED = "leave_rejected", "Leave Rejected"
        LEAVE_CANCELLED = "leave_cancelled", "Leave Cancelled"
        LEAVE_POLICY_UPDATED = "leave_policy_updated", "Leave Policy Updated"
        PAYROLL_RUN = "payroll_run", "Payroll Run Generated"
        PAYROLL_PROFILE_SAVED = "payroll_profile_saved", "Payroll Profile Saved"
        HOLIDAY_ADDED = "holiday_added", "Holiday Added"
        HOLIDAY_REMOVED = "holiday_removed", "Holiday Removed"
        PROJECT_STAGE = "project_stage", "Project Stage Changed"
        PROJECT_LOG = "project_log", "Project Log Entry"
        PROJECT_PLAN = "project_plan", "Project Plan Updated"
        PROJECT_TEAM = "project_team", "Project Pod Changed"
        PROJECT_CRUNCH = "project_crunch", "Project Crunch"

    event_type = models.CharField(max_length=30, choices=EventType.choices)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    target_content_type = models.CharField(max_length=100, blank=True, default="")
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.event_type}] {self.title}"


class Todo(models.Model):
    """A private to-do item on the home page. Only its owner ever sees it."""

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todos")
    # Needed for the bell and the DSR, which are per company. Null only for rows made before it existed.
    company = models.ForeignKey("accounts.Company", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    text = models.CharField(max_length=300)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.MEDIUM)
    done = models.BooleanField(default=False)
    due = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    hours_spent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["done", "-created_at"]

    def __str__(self):
        return self.text

    @property
    def dsr_source_id(self):
        return f"todo-{self.pk}"

    @property
    def elapsed_display(self):
        """Human-readable time span between created_at and completed_at (or now)."""
        end = self.completed_at or timezone.now()
        seconds = max(0, int((end - self.created_at).total_seconds()))
        days, rem = divmod(seconds, 86400)
        hours, mins = divmod(rem, 3600)
        minutes = mins // 60
        if days > 0:
            return f"{days}d {hours}h" if hours else f"{days}d"
        if hours > 0:
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"
        if minutes > 0:
            return f"{minutes}m"
        return "< 1m"

    @property
    def suggested_time_input(self):
        """Suggested prefill for the time input box."""
        if self.hours_spent is not None and self.hours_spent > 0:
            from apps.dsr.duration import format_hm
            return format_hm(self.hours_spent)
        end = self.completed_at or timezone.now()
        seconds = max(0, int((end - self.created_at).total_seconds()))
        if seconds > 28800:
            return "1h"
        minutes = max(15, round((seconds / 60) / 15) * 15)
        hours, mins = divmod(minutes, 60)
        if hours > 0 and mins > 0:
            return f"{hours}h {mins}m"
        if hours > 0:
            return f"{hours}h"
        return f"{mins}m"

    @property
    def hours_display(self):
        """Formatted string for display badge, e.g. 1h 30m or 45m."""
        if not self.hours_spent:
            return ""
        from apps.dsr.duration import format_hm
        return format_hm(self.hours_spent)

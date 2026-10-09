from django.conf import settings
from django.db import models

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

    class Meta:
        ordering = ["done", "-created_at"]

    def __str__(self):
        return self.text

    @property
    def dsr_source_id(self):
        return f"todo-{self.pk}"

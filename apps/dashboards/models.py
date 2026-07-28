from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class ActivityLog(TenantScopedModel):
    class EventType(models.TextChoices):
        ERROR_CAPTURED = "error_captured", "Error Captured"
        ERROR_RESOLVED = "error_resolved", "Error Resolved"
        TICKET_CREATED = "ticket_created", "Ticket Created"
        TICKET_RESOLVED = "ticket_resolved", "Ticket Resolved"
        FEEDBACK_RECEIVED = "feedback_received", "Feedback Received"
        SURVEY_RESPONSE = "survey_response", "Survey Response"
        MEMBER_JOINED = "member_joined", "Member Joined"
        MEMBER_REMOVED = "member_removed", "Member Removed"
        PRODUCT_CREATED = "product_created", "Product Created"
        AUTO_TICKET = "auto_ticket", "Auto Ticket Created"

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

from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class Notification(TenantScopedModel):
    """Something that happened that one person should know about.

    One row per recipient. The bell reads these, and `service.notify` is the only
    thing that creates them, so every notification is also pushed live and, where
    the person has subscribed, to their phone.
    """

    class Kind(models.TextChoices):
        ASSIGNED = "assigned", "Assigned to you"
        MENTION = "mention", "Mentioned you"
        COMMENT = "comment", "New comment"
        LEAVE_REQUEST = "leave_request", "Leave request"
        LEAVE_DECISION = "leave_decision", "Leave decision"
        CORRECTION_REQUEST = "correction_request", "Attendance correction request"
        CORRECTION_DECISION = "correction_decision", "Attendance correction decision"
        PAYSLIP = "payslip", "Payslip ready"
        REGRESSION = "regression", "Error came back"
        SYSTEM = "system", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, default=Kind.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=300, blank=True, default="")
    # Always a site-relative path, validated in `service.safe_path`.
    url = models.CharField(max_length=255, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at", "-created_at"])]

    def __str__(self):
        return f"{self.kind} for {self.user_id}: {self.title}"

    @property
    def is_read(self):
        return self.read_at is not None

    def as_json(self):
        return {
            "id": self.pk,
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "url": f"/notifications/{self.pk}/open/",
            "actor": (self.actor.get_full_name() or self.actor.username) if self.actor else "",
            "created_at": self.created_at.isoformat(),
            "read": self.is_read,
        }


class PushSubscription(models.Model):
    """A browser or phone that asked for notifications while the app is closed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"push for {self.user_id}"

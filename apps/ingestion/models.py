import hashlib
import json

from django.db import models

from apps.core.models import TenantScopedModel


def compute_fingerprint(error_type, message, stacktrace):
    raw = f"{error_type}:{message}:{stacktrace[:500]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class ErrorGroup(TenantScopedModel):
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("info", "Info"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("investigating", "Investigating"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="error_groups",
    )
    fingerprint = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=500)
    error_type = models.CharField(max_length=255, blank=True, default="")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    occurrence_count = models.PositiveIntegerField(default=1)
    affected_user_count = models.PositiveIntegerField(default=0)

    class Meta(TenantScopedModel.Meta):
        unique_together = ("product", "fingerprint")
        ordering = ["-last_seen"]

    def __str__(self):
        return f"[{self.severity}] {self.title} (x{self.occurrence_count})"


class ErrorOccurrence(TenantScopedModel):
    error_group = models.ForeignKey(
        ErrorGroup,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    version = models.ForeignKey(
        "products.ProductVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    environment = models.CharField(max_length=20, blank=True, default="production")
    stacktrace = models.TextField(blank=True, default="")
    user_ref = models.CharField(max_length=255, blank=True, default="")
    page = models.CharField(max_length=500, blank=True, default="")
    device = models.CharField(max_length=255, blank=True, default="")
    os = models.CharField(max_length=100, blank=True, default="")
    browser = models.CharField(max_length=100, blank=True, default="")
    request_payload = models.JSONField(null=True, blank=True)
    raw_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"Occurrence of {self.error_group.title}"


class Feedback(TenantScopedModel):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    version = models.ForeignKey(
        "products.ProductVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    user_ref = models.CharField(max_length=255, blank=True, default="")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, default="")
    screenshot_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback ({self.rating}/5) for {self.product.name}"


class IngestedTicket(TenantScopedModel):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="ingested_tickets",
    )
    external_id = models.CharField(max_length=255, blank=True, default="")
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    ticket_type = models.CharField(
        max_length=20,
        choices=[
            ("bug", "Bug"),
            ("feature", "Feature"),
            ("question", "Question"),
        ],
        default="bug",
    )
    user_ref = models.CharField(max_length=255, blank=True, default="")
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ingested: {self.title}"

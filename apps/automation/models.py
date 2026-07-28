from django.db import models

from apps.core.models import TenantScopedModel


class AutoTicketRule(TenantScopedModel):
    class TriggerType(models.TextChoices):
        ERROR_THRESHOLD = "error_threshold", "Error Occurrence Threshold"
        NEW_ERROR = "new_error", "New Error Group"

    class ActionType(models.TextChoices):
        CREATE_TICKET = "create_ticket", "Create Ticket"
        NOTIFY_ONLY = "notify_only", "Notify Only"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="auto_ticket_rules",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    trigger_type = models.CharField(
        max_length=30,
        choices=TriggerType.choices,
        default=TriggerType.ERROR_THRESHOLD,
    )
    severity = models.CharField(
        max_length=20,
        choices=[
            ("", "Any"),
            ("critical", "Critical"),
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
        ],
        blank=True,
        default="",
    )
    threshold_count = models.PositiveIntegerField(
        default=10,
        help_text="Number of occurrences to trigger within the time window.",
    )
    window_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Time window in minutes.",
    )
    action = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        default=ActionType.CREATE_TICKET,
    )
    assign_to = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auto_assigned_rules",
    )
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_trigger_type_display()})"


class AutoTicketLog(TenantScopedModel):
    rule = models.ForeignKey(
        AutoTicketRule,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    error_group = models.ForeignKey(
        "ingestion.ErrorGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    matched_count = models.PositiveIntegerField(default=0)
    action_taken = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"Log for {self.rule.name} - {self.action_taken}"

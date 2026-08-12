from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class Ticket(TenantScopedModel):
    class TicketType(models.TextChoices):
        BUG = "bug", "Bug"
        FEATURE = "feature", "Feature"
        QUESTION = "question", "Question"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        TESTING = "testing", "Testing"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO = "auto", "Automatic"
        PORTAL = "customer_portal", "Customer Portal"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    ticket_type = models.CharField(
        max_length=20,
        choices=TicketType.choices,
        default=TicketType.BUG,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="tickets_assigned",
        blank=True,
    )
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional due date. Overdue tickets are highlighted.",
    )
    linked_error_group = models.ForeignKey(
        "ingestion.ErrorGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    milestone = models.ForeignKey(
        "products.ProductMilestone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.title}"

    def can_transition_to(self, new_status):
        return new_status in dict(Ticket.Status.choices)

    @property
    def valid_next_statuses(self):
        return [(v, l) for v, l in Ticket.Status.choices if self.can_transition_to(v)]

    @property
    def is_overdue(self):
        return bool(
            self.deadline
            and self.status not in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED)
            and self.deadline < timezone.now()
        )

    def transition_to(self, new_status, actor=None):
        if not self.can_transition_to(new_status):
            raise ValueError(f"'{new_status}' is not a valid status.")
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])
        if new_status in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED):
            try:
                from apps.dsr.service import auto_log_ticket_dsr
                auto_log_ticket_dsr(self, actor=actor)
            except Exception:
                pass

    def set_assignees(self, users):
        """Replace the assignee set and keep the primary ``assigned_to`` in sync."""
        self.assignees.set(users)
        primary = self.assignees.order_by("pk").first()
        self.assigned_to = primary
        self.save(update_fields=["assigned_to", "updated_at"])


class TicketComment(TenantScopedModel):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on #{self.ticket_id}"


class TicketAttachment(TenantScopedModel):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return self.file_name

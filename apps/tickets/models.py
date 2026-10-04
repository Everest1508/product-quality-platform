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
    # Position within the product (1, 2, 3...). Shown as AUM-001 with the product key.
    number = models.PositiveIntegerField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "number"],
                condition=models.Q(number__isnull=False),
                name="ticket_number_unique_per_product",
            ),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # Remember which product the number was issued by, so moving a ticket to
        # another product can hand it a number from that product instead.
        instance._number_product_id = instance.__dict__.get("product_id")
        return instance

    def save(self, *args, **kwargs):
        moved = (
            not self._state.adding
            and getattr(self, "_number_product_id", self.product_id) != self.product_id
        )
        if self.product_id is None:
            self.number = None
        elif self.number is None or moved:
            self.number = self._next_number()
        super().save(*args, **kwargs)
        self._number_product_id = self.product_id

    def _next_number(self):
        from django.db import transaction
        from django.db.models import F

        from apps.products.models import Product

        # One UPDATE, then a read, inside a transaction: two tickets created at the
        # same moment cannot be given the same number.
        with transaction.atomic():
            Product.objects.filter(pk=self.product_id).update(ticket_counter=F("ticket_counter") + 1)
            return Product.objects.values_list("ticket_counter", flat=True).get(pk=self.product_id)

    @property
    def key(self):
        """AUM-001, or #12 for a ticket that has no product."""
        if self.product_id and self.number:
            return f"{self.product.key}-{self.number:03d}"
        return f"#{self.pk}"

    def __str__(self):
        return f"{self.key} {self.title}"

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

    def set_assignees(self, users, actor=None):
        """Replace the assignee set and keep the primary ``assigned_to`` in sync.

        Anyone newly added is notified (not the person who made the change).
        """
        before = set(self.assignees.values_list("pk", flat=True))
        self.assignees.set(users)
        primary = self.assignees.order_by("pk").first()
        self.assigned_to = primary
        self.save(update_fields=["assigned_to", "updated_at"])

        added = self.assignees.exclude(pk__in=before)
        if added:
            from apps.notifications import service
            from apps.notifications.models import Notification

            service.notify_many(
                added,
                company=self.company,
                kind=Notification.Kind.ASSIGNED,
                title=f"You were assigned ticket {self.key}",
                body=self.title,
                url=f"/tickets/{self.pk}/",
                actor=actor,
            )


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
    # People named with @username who can open the ticket. See tickets/mentions.py.
    mentions = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="+",
    )
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

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TenantScopedModel


class LeavePolicy(TenantScopedModel):
    """A company's rules for one kind of leave, e.g. casual or sick.

    Both limits are optional: ``max_days_per_year`` of ``None`` means the type
    is uncapped (which is what unpaid leave usually wants), and
    ``max_consecutive_days`` of ``None`` means long spells are allowed.
    """

    name = models.CharField(max_length=60)
    max_days_per_year = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Leave days allowed per calendar year. Blank means unlimited.",
    )
    max_consecutive_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.5"))],
        help_text="Longest single spell allowed. Blank means unlimited.",
    )
    is_paid = models.BooleanField(default=True)
    color = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Optional CSS colour token for badges, e.g. green or amber.",
    )
    icon = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text="Optional icon name from apps.core.icons.ICONS, e.g. coffee.",
    )

    # A closed set of tokens, not free text. The value lands in a class name in
    # the templates, so anything not listed here must never reach the database.
    COLOR_TOKENS = (
        ("", "No colour"),
        ("green", "Green"),
        ("amber", "Amber"),
        ("red", "Red"),
        ("blue", "Blue"),
        ("purple", "Purple"),
        ("grey", "Grey"),
    )
    COLOR_NAMES = tuple(token for token, _label in COLOR_TOKENS)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"], name="uniq_leave_policy_name_per_company"
            )
        ]
        verbose_name = "Leave Policy"
        verbose_name_plural = "Leave Policies"

    def __str__(self):
        return f"{self.name} @ {self.company.name}"

    @property
    def annual_limit_label(self):
        return "Unlimited" if self.max_days_per_year is None else f"{self.max_days_per_year} days / year"

    @property
    def consecutive_limit_label(self):
        return (
            "Unlimited"
            if self.max_consecutive_days is None
            else f"{self.max_consecutive_days} days at a time"
        )


class LeaveRequest(TenantScopedModel):
    """One employee's application for a spell of leave.

    ``days`` is the charge against the balance and is always working days
    (Mon-Fri), so a Friday-to-Monday spell costs 2 days, not 4. A half day is
    0.5 and may only be requested for a single date.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    # Literal values, matching how queries filter status elsewhere.
    OPEN_STATUSES = ("pending", "approved")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    policy = models.ForeignKey(
        LeavePolicy,
        # CASCADE, not PROTECT: deleting a company must tear down its leave
        # data. PROTECT here would block company deletion outright.
        on_delete=models.CASCADE,
        related_name="requests",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField()
    is_half_day = models.BooleanField(default=False)
    days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=Decimal("0.0"),
        help_text="Charge against the balance, in working days.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reason = models.TextField(blank=True, default="")

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]
        verbose_name = "Leave Request"
        verbose_name_plural = "Leave Requests"

    def __str__(self):
        return f"{self.user.username} {self.policy.name} {self.start_date}→{self.end_date}"

    def clean(self):
        errors = {}
        if self.end_date and self.start_date and self.end_date < self.start_date:
            errors["end_date"] = "End date cannot be before the start date."
        if self.is_half_day and self.start_date and self.end_date:
            if self.start_date != self.end_date:
                errors["is_half_day"] = "A half day can only be taken on a single date."
        if errors:
            raise ValidationError(errors)

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def span_label(self):
        if self.start_date == self.end_date:
            return self.start_date.strftime("%d %b %Y")
        return f"{self.start_date.strftime('%d %b')} – {self.end_date.strftime('%d %b %Y')}"

    @property
    def days_label(self):
        from apps.leave.service import format_days

        value = format_days(self.days)
        return f"{value} day" if value == "1" else f"{value} days"
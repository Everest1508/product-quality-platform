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

    Neither limit *blocks* a request any more. Both cap how many days are
    **paid**: exceed one and the excess is charged as unpaid leave rather than
    refused, so a genuine emergency is never impossible to book. That is why the
    help text says "paid" -- "capped at 3" next to a request that books 10 would
    be a lie.
    """

    name = models.CharField(max_length=60)
    max_days_per_year = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text=(
            "Paid leave days allowed per calendar year. Blank means unlimited. "
            "Days beyond this are charged as unpaid leave, not refused."
        ),
    )
    max_consecutive_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.5"))],
        help_text=(
            "Paid days in a single spell. Blank means unlimited. Days beyond "
            "this are charged as unpaid leave, not refused."
        ),
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
        return "No cap" if self.max_days_per_year is None else f"{self.max_days_per_year} paid days / year"

    @property
    def consecutive_limit_label(self):
        # "paid days", because the cap no longer bounds the spell -- it bounds
        # how much of it is paid. Logging "3 days at a time" next to an approved
        # 10-day request is a contradiction on the audit trail.
        return (
            "No cap"
            if self.max_consecutive_days is None
            else f"{self.max_consecutive_days} paid days at a time"
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

    class SplitMode(models.TextChoices):
        """How the paid/unpaid split on this request was arrived at.

        AUTO is the server's own arithmetic (paid up to the remaining allowance
        and the spell cap, the rest unpaid). MANUAL is an approver's deliberate
        override. The mode is stored rather than inferred so a payslip can say
        which it was, and so nothing recomputes an approver's decision later.
        """

        AUTO = "auto", "Automatic"
        MANUAL = "manual", "Manual"

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
    # The paid/unpaid split, stored rather than read live off the policy. Two
    # reasons, both about history: an approver can overrule the policy per
    # request, and a later edit to the policy must not rewrite what a payslip
    # was already priced from. `null` means "not split yet", which is what every
    # row saved before this existed is -- see `split`.
    paid_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Days paid. Null on rows predating the split; see split.",
    )
    unpaid_days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Days charged as unpaid. Null on rows predating the split.",
    )
    split_mode = models.CharField(
        max_length=10,
        choices=SplitMode.choices,
        default=SplitMode.AUTO,
        help_text="Automatic, or an approver's manual override.",
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
    def split(self):
        """`{"paid": Decimal, "unpaid": Decimal}` for this request.

        A row saved before the split existed carries `paid_days = NULL`, so the
        whole charge falls on whichever bucket its policy said at the time. That
        is not a guess about old data, it is the only honest reading: the split
        was a property of the policy then, and inventing one now would restate
        somebody's approved leave.
        """
        if self.paid_days is not None:
            return {
                "paid": self.paid_days,
                "unpaid": self.unpaid_days or Decimal("0.0"),
            }
        if self.policy.is_paid:
            return {"paid": self.days, "unpaid": Decimal("0.0")}
        return {"paid": Decimal("0.0"), "unpaid": self.days}

    @property
    def is_fully_paid(self):
        return self.split["unpaid"] <= 0

    @property
    def is_fully_unpaid(self):
        return self.split["paid"] <= 0

    @property
    def split_label(self):
        """'3 paid', '2 unpaid' or '2 paid, 1 unpaid'."""
        from apps.leave.service import format_days

        paid = self.split["paid"]
        unpaid = self.split["unpaid"]
        if unpaid <= 0:
            return f"{format_days(paid)} paid"
        if paid <= 0:
            return f"{format_days(unpaid)} unpaid"
        return f"{format_days(paid)} paid, {format_days(unpaid)} unpaid"

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
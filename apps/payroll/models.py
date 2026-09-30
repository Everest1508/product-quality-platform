from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class Holiday(TenantScopedModel):
    """A company holiday.

    Excluded from working days, so a person on a festival week is not paid for
    days the company was shut. One row per date; the unique_together stops the
    same holiday being added twice.
    """

    date = models.DateField(db_index=True)
    name = models.CharField(max_length=120)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-date"]
        unique_together = ("company", "date")
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"

    def __str__(self):
        return f"{self.name} — {self.date}"


class PayrollProfile(TenantScopedModel):
    """How one person is paid, effective from a date.

    Dated rather than a field on the user, because a rate change must not
    rewrite payslips already generated for earlier periods.

    Pay is a **monthly salary**, because that is the number someone actually
    knows. The daily rate is derived from it per cycle and is never entered:
    Sat, Sun and company holidays are already out of the working-day count, so
    the divisor is the real one and the person is paid their whole salary.

    ``daily_rate`` is the fallback for anyone paid by the day, and is what rows
    saved before monthly salary existed keep using. Set ``monthly_salary`` and
    it takes over; leave it empty and the daily rate is used as typed.

    ``is_on_payroll`` is the switch that decides who gets a payslip at all:
    service accounts and bots stay unticked, so they are skipped by a run
    instead of silently receiving a zero-salary slip.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payroll_profiles",
    )
    monthly_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Gross monthly salary, before any unpaid leave deduction.",
    )
    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Used only when there is no monthly salary.",
    )
    currency = models.CharField(max_length=8, default="INR")
    effective_from = models.DateField(default=timezone.localdate)
    is_on_payroll = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["user__username", "-effective_from"]
        unique_together = ("company", "user", "effective_from")
        verbose_name = "Payroll Profile"
        verbose_name_plural = "Payroll Profiles"

    def __str__(self):
        if self.monthly_salary:
            return f"{self.user.username} @ {self.monthly_salary}/month"
        return f"{self.user.username} @ {self.daily_rate}/day"


class PayrollRun(TenantScopedModel):
    """One payroll cycle, from the 27th of a month to the 26th of the next.

    Payslips point at a run, so a cycle keeps its own identity and the numbers
    on it are never recomputed behind the user's back.
    """

    period_start = models.DateField()
    period_end = models.DateField(db_index=True)
    working_days = models.PositiveIntegerField(
        default=0,
        help_text="Working days in the cycle, after weekends and holidays.",
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="A locked run cannot be recalculated.",
    )
    generated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-period_start"]
        unique_together = ("company", "period_start", "period_end")
        verbose_name = "Payroll Run"
        verbose_name_plural = "Payroll Runs"

    def __str__(self):
        return f"{self.period_start} → {self.period_end}"

    @property
    def label(self):
        return f"{self.period_start:%d %b %Y} → {self.period_end:%d %b %Y}"

    @property
    def total_gross(self):
        return sum((p.gross for p in self.payslips.all()), Decimal("0.00"))

    @property
    def total_deduction(self):
        return sum((p.deduction for p in self.payslips.all()), Decimal("0.00"))


class Payslip(TenantScopedModel):
    """One person's pay for one cycle.

    The day counts and amounts are copied in at generation time instead of
    being derived on the fly, so editing a rate, a leave request or a holiday
    afterwards never changes a payslip that was already issued.
    """

    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="payslips",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payslips",
    )
    profile = models.ForeignKey(
        PayrollProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payslips",
    )
    currency = models.CharField(max_length=8, default="INR")
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)

    working_days = models.PositiveIntegerField(default=0)
    paid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    unpaid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    payable_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Lateness is snapshotted like everything else on a payslip: editing a
    # punch afterwards must not silently rewrite an already-issued slip.
    late_half_days = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Days lost to arriving more than an hour after shift start.",
    )
    late_penalty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Cash penalty for late arrivals inside the grace bands.",
    )
    breakdown = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["user__username"]
        unique_together = ("run", "user")
        verbose_name = "Payslip"
        verbose_name_plural = "Payslips"

    def __str__(self):
        return f"{self.user.username} — {self.gross}"

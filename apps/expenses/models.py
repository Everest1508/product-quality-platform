from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class Expense(TenantScopedModel):
    """One thing somebody paid for.

    The amount is whole paise, never a float or a DecimalField: splits are plain
    sums are plain integer maths, and SQLite cannot hand a bad decimal back as a number.
    """

    class Category(models.TextChoices):
        TEA = "tea", "Tea"
        MILK = "milk", "Milk"
        AI = "ai", "AI subscription"
        SERVER = "server", "Server rent"
        TRIP = "trip", "Team trip"
        OTHER = "other", "Other"

    amount_paise = models.PositiveBigIntegerField()
    date = models.DateField()
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    # What "Other" means, typed by the person adding it.
    category_other = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=255, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_paid")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_created")
    created_at = models.DateTimeField(auto_now_add=True)
    # Pay the payer back through salary: the next payroll run for a cycle ending
    # on or after `date` adds it to their payslip and sets `paid_in_run`.
    to_salary = models.BooleanField(default=False)
    # Or paid back by hand (cash, UPI): the day it was done. Never both.
    repaid_on = models.DateField(null=True, blank=True)
    paid_in_run = models.ForeignKey(
        "payroll.PayrollRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses"
    )

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def category_label(self):
        return self.category_other or self.get_category_display()

    def __str__(self):
        return f"{self.category_label} ({self.amount_paise / 100:.2f})"


class ExpenseComment(TenantScopedModel):
    """One line of talk about an expense, between the owners and admins.

    Shaped like `TicketComment`: it belongs to its parent, keeps its author when
    the author is later removed (shown as "Someone"), and has no edit, only a
    delete by the person who wrote it.
    """

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Comment by {self.author} on expense {self.expense_id}"

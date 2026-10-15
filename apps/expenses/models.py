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

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def category_label(self):
        return self.category_other or self.get_category_display()

    def __str__(self):
        return f"{self.category_label} ({self.amount_paise / 100:.2f})"

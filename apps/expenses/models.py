from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class Expense(TenantScopedModel):
    """One thing somebody paid for, shared between some of the team.

    The amount is whole paise, never a float or a DecimalField: splits are plain
    integer maths, and SQLite cannot hand a bad decimal back as a number.
    """

    class Category(models.TextChoices):
        FOOD = "food", "Food & drinks"
        TRAVEL = "travel", "Travel"
        OFFICE = "office", "Office"
        SOFTWARE = "software", "Software"
        OTHER = "other", "Other"

    title = models.CharField(max_length=120)
    amount_paise = models.PositiveBigIntegerField()
    date = models.DateField()
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    note = models.CharField(max_length=255, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_paid")
    split_with = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="expenses_shared")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expenses_created")
    created_at = models.DateTimeField(auto_now_add=True)
    # Null until somebody settles up; "open" means not settled.
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.title} ({self.amount_paise / 100:.2f})"

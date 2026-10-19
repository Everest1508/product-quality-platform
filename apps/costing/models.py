from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class Estimate(TenantScopedModel):
    """A project cost estimate. Every number on it is typed by an owner or admin.

    Nothing is read from payroll, attendance or the rate cards: the salaries are
    entered here by hand and stay on this row. `people` and `others` are lists of
    plain dicts (see `service.clean_rows`), kept as JSON because they are only
    ever read and written together with their estimate. Money is stored as text
    so a Decimal survives the round trip exactly.
    """

    name = models.CharField(max_length=200)
    client_name = models.CharField(max_length=200, blank=True)
    dedicated_days = models.PositiveIntegerField(default=45)
    client_days = models.PositiveIntegerField(default=60)
    quote_date = models.DateField(default=timezone.localdate, help_text="When it was quoted; set it for old quotes.")
    rent_monthly = models.CharField(max_length=20, default="0")
    ai_per_person_month = models.CharField(max_length=20, default="0")
    margin_percent = models.CharField(max_length=12, default="50")
    margin_mode = models.CharField(max_length=8, default="markup")
    pitch_price = models.CharField(max_length=20, blank=True)
    people = models.JSONField(default=list, blank=True)
    others = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-quote_date", "-id"]

    def inputs(self):
        return {f: getattr(self, f) for f in INPUT_FIELDS}

    def __str__(self):
        return self.name


INPUT_FIELDS = (
    "name", "client_name", "quote_date", "dedicated_days", "client_days", "rent_monthly", "ai_per_person_month",
    "margin_percent", "margin_mode", "pitch_price", "people", "others",
)

import secrets

from django.db import models

from apps.core.models import TenantScopedModel


def new_token():
    return secrets.token_urlsafe(32)


class LeadWebhook(models.Model):
    """One secret per company; the token in the URL is what ties a form post to a workspace."""

    company = models.OneToOneField("accounts.Company", on_delete=models.CASCADE, related_name="lead_webhook")
    token = models.CharField(max_length=64, unique=True, default=new_token)


class Lead(TenantScopedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        CONVERTED = "converted", "Converted"
        LOST = "lost", "Lost"

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True, default="")  # free text: "+91 98765 43210"
    company_name = models.CharField(max_length=200, blank=True, default="")
    need = models.CharField(max_length=100, blank=True, default="")  # free text: the website owns the options
    details = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    # Set when the lead is converted: the project made from it.
    product = models.ForeignKey("products.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="source_leads")
    converted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class LeadLog(models.Model):
    """One line of what was done on a lead: a call, a note, a status change, the conversion."""

    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        STATUS = "status", "Status"
        CONVERTED = "converted", "Converted"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="logs")
    author = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.NOTE)
    text = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

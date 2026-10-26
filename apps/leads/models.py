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
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    company_name = models.CharField(max_length=200, blank=True, default="")
    need = models.CharField(max_length=100, blank=True, default="")  # free text: the website owns the options
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

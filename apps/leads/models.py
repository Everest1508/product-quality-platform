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
        GENERATED = "generated", "Generated"
        REQ_GATHERING = "req_gathering", "Requirement gathering"
        ESTIMATION = "estimation", "Timeline & cost estimation"
        QUOTE_SENT = "quote_sent", "Quotation sent"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")  # website leads always have one; hand-entered ones may not
    phone = models.CharField(max_length=40, blank=True, default="")  # free text: "+91 98765 43210"
    company_name = models.CharField(max_length=200, blank=True, default="")
    industry = models.CharField(max_length=100, blank=True, default="")
    need = models.CharField(max_length=100, blank=True, default="")  # free text: the website owns the options
    details = models.TextField()
    # True until an admin clicks "convert to lead". Website form posts land here as
    # submissions; they only appear on the pipeline board once this is cleared.
    is_submission = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.GENERATED)
    # Asked for when the lead moves to Quotation sent / Won. Admin-only pages are the only place they show.
    quoted_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    won_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
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
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        MESSAGE = "message", "Message"
        STATUS = "status", "Moved"
        CONVERTED = "converted", "Converted"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="logs")
    author = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.NOTE)
    title = models.CharField(max_length=200, blank=True, default="")
    text = models.CharField(max_length=2000, blank=True, default="")  # the details, or the reason for a move
    # Filled for a move, so the page can draw "A to B, amount" instead of parsing text.
    from_status = models.CharField(max_length=14, blank=True, default="")
    to_status = models.CharField(max_length=14, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def from_label(self):
        return dict(Lead.Status.choices).get(self.from_status, "")

    @property
    def to_label(self):
        return dict(Lead.Status.choices).get(self.to_status, "")

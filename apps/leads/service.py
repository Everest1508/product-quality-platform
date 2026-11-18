from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.dashboards.service import log_activity
from apps.leads.models import Lead, LeadLog
from apps.products.models import Product


def add_log(lead, author, text, kind=LeadLog.Kind.NOTE, title="", **move):
    return LeadLog.objects.create(lead=lead, author=author, kind=kind, title=title, text=text, **move)


def set_status(lead, status, actor, amount=None, reason=""):
    """Move a lead. Quotation sent and Won each need an amount; the caller validates it."""
    if status == lead.status:
        return
    old = lead.status
    fields = ["status"]
    lead.status = status
    if status == Lead.Status.QUOTE_SENT:
        lead.quoted_amount = amount
        fields.append("quoted_amount")
    elif status == Lead.Status.WON:
        lead.won_amount = amount
        fields.append("won_amount")
    else:
        amount = None
    lead.save(update_fields=fields)
    add_log(lead, actor, reason, LeadLog.Kind.STATUS, from_status=old, to_status=status, amount=amount)


def _free_name(company, base):
    name, n = base, 2
    while Product.objects.filter(company=company, slug=slugify(name)).exists():
        name = f"{base} {n}"
        n += 1
    return name


@transaction.atomic
def convert(lead, actor):
    """Turn a lead into a project, once. Returns the project (the existing one if already converted)."""
    if lead.product_id:
        return lead.product
    base = lead.company_name or lead.full_name
    product = Product(
        company=lead.company,
        name=_free_name(lead.company, base),
        description=lead.details[:2000],
        lead=actor,
    )
    product.slug = slugify(product.name)
    product.save()
    lead.product = product
    lead.converted_at = timezone.now()
    lead.save(update_fields=["product", "converted_at"])
    add_log(lead, actor, f"Converted to project {product.name}", LeadLog.Kind.CONVERTED)
    log_activity(
        lead.company, "product_created", f"Project '{product.name}' created from a website lead",
        description=lead.full_name, actor=actor, target_content_type="product", target_object_id=product.pk,
    )
    return product

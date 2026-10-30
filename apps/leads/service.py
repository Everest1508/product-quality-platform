from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.dashboards.service import log_activity
from apps.leads.models import Lead, LeadLog
from apps.products.models import Product


def add_log(lead, author, text, kind=LeadLog.Kind.NOTE):
    return LeadLog.objects.create(lead=lead, author=author, kind=kind, text=text)


def set_status(lead, status, actor):
    """Move a lead to a status other than Converted (that one is `convert`, which makes the project)."""
    if status == lead.status:
        return
    old = lead.get_status_display()
    lead.status = status
    lead.save(update_fields=["status"])
    add_log(lead, actor, f"Status: {old} to {lead.get_status_display()}", LeadLog.Kind.STATUS)


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
    lead.status = Lead.Status.CONVERTED
    lead.converted_at = timezone.now()
    lead.save(update_fields=["product", "status", "converted_at"])
    add_log(lead, actor, f"Converted to project {product.name}", LeadLog.Kind.CONVERTED)
    log_activity(
        lead.company, "product_created", f"Project '{product.name}' created from a website lead",
        description=lead.full_name, actor=actor, target_content_type="product", target_object_id=product.pk,
    )
    return product

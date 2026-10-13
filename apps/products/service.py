"""Product actions with their side effects (activity log), shared by the JSON API.

Access checks stay with the caller (the view layer); these functions assume the
person may touch the product.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Membership
from apps.core.timefmt import t12
from apps.dashboards.service import log_activity
from apps.products.forms import ProductCreateForm, ProductEditForm, VersionCreateForm
from apps.products.keys import unique_key
from apps.products.models import APIKey, Product, ProductAccess, ProductMilestone

# Who may create, rotate and revoke keys. A key lets an application write into the
# product, so it is for the people who work on it, not for viewers or support.
KEY_MANAGER_ROLES = ("owner", "admin", "developer")
ROTATE_GRACE = {"now": None, "1d": timedelta(days=1), "7d": timedelta(days=7)}


def suggest_key(company, name, exclude_pk=None):
    taken = Product.objects.filter(company=company)
    if exclude_pk:
        taken = taken.exclude(pk=exclude_pk)
    return unique_key(name[:255], set(taken.values_list("key", flat=True)))


def _parse_date(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return timezone.localdate()


def add_milestones(product, rows):
    """`rows` are {title, date} from the product form; blank rows are skipped,
    a bad date falls back to today. They go after the milestones already there."""
    start = product.milestones.count()
    n = 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        title = row.get("title")
        title = title.strip() if isinstance(title, str) else ""
        if not title or not row.get("date"):
            continue
        n += 1
        ProductMilestone.objects.create(
            company=product.company, product=product, title=title[:255], target_date=_parse_date(row["date"]),
            order=start + n, status=ProductMilestone.Status.UPCOMING,
        )


def create_product(data, milestones, actor, company):
    """Returns (product, form); product is None when the form is invalid."""
    form = ProductCreateForm(data, company=company)
    if not form.is_valid():
        return None, form
    product = form.save()
    add_milestones(product, milestones)
    log_activity(
        company, "product_created", f"Product '{product.name}' created", description=product.description[:200],
        actor=actor, target_content_type="product", target_object_id=product.pk,
    )
    return product, form


def update_product(data, milestones, product, actor, company):
    form = ProductEditForm(data, instance=product)
    if not form.is_valid():
        return None, form
    form.save()
    add_milestones(product, milestones)
    log_activity(
        company, "product_updated", f"Product '{product.name}' updated", actor=actor,
        target_content_type="product", target_object_id=product.pk,
    )
    return product, form


def delete_product(product, actor, company):
    name, pk = product.name, product.pk
    product.delete()
    log_activity(
        company, "product_deleted", f"Product '{name}' deleted", actor=actor,
        target_content_type="product", target_object_id=pk,
    )
    return name


def add_version(data, product, actor, company):
    """Returns (version, form); version is None when the form is invalid."""
    form = VersionCreateForm(data)
    if not form.is_valid():
        return None, form
    version = form.save(commit=False)
    version.product, version.company = product, company
    if version.is_current:
        product.versions.filter(is_current=True).update(is_current=False)
    version.save()
    log_activity(
        company, "version_added", f"Version '{version.version_string}' added to {product.name}", actor=actor,
        target_content_type="version", target_object_id=version.pk,
        metadata={"product_id": product.pk, "is_current": version.is_current},
    )
    return version, form


def delete_version(version, actor, company):
    product, text, pk = version.product, version.version_string, version.pk
    version.delete()
    log_activity(
        company, "version_removed", f"Version '{text}' removed from {product.name}", actor=actor,
        target_content_type="version", target_object_id=pk, metadata={"product_id": product.pk},
    )
    return text


def create_key(product, name, actor, company):
    name = name.strip()[:100] if isinstance(name, str) else ""
    name = name or "default"
    key, raw = APIKey.create_key(product=product, name=name)
    log_activity(
        company, "api_key_created", f"API key '{name}' created for {product.name}", actor=actor,
        target_content_type="api_key", target_object_id=key.pk, metadata={"product_id": product.pk},
    )
    return key, raw


def revoke_key(key, actor, company):
    key.is_active = False
    key.revoked_at = timezone.now()
    key.save(update_fields=["is_active", "revoked_at"])
    log_activity(
        company, "api_key_revoked", f"API key '{key.name}' revoked", actor=actor,
        target_content_type="api_key", target_object_id=key.pk, metadata={"product_id": key.product_id},
    )


def rotate_key(old, grace, actor, company):
    """Replace a key without an outage. The old one is revoked now, or keeps
    working for a day or a week so the application can be switched first.

    Returns (new_key, raw, message), or (None, None, error)."""
    if not isinstance(grace, str) or grace not in ROTATE_GRACE:
        return None, None, "Unknown grace period."
    if not old.is_usable:
        return None, None, "Only a working key can be rotated."
    new_key, raw = APIKey.create_key(product=old.product, name=old.name)
    now = timezone.now()
    delta = ROTATE_GRACE[grace]
    if delta is None:
        old.is_active, old.revoked_at, old.expires_at = False, now, None
    else:
        end = now + delta
        old.expires_at = min(old.expires_at, end) if old.expires_at else end
    old.save(update_fields=["is_active", "revoked_at", "expires_at"])
    log_activity(
        company, "api_key_rotated", f"API key '{old.name}' rotated for {old.product.name}",
        description="Old key revoked now" if delta is None else f"Old key works until {old.expires_at:%b %d}, {t12(old.expires_at)}",
        actor=actor, target_content_type="api_key", target_object_id=new_key.pk,
        metadata={"product_id": old.product_id, "old_key_id": old.pk, "grace": grace},
    )
    message = (
        "Key rotated — the old key is revoked now."
        if delta is None else f"Key rotated — the old key works until {old.expires_at:%b %d}."
    )
    return new_key, raw, message


def grant_access(product, user_id, actor, company):
    """Returns an error message, or None. Idempotent: granting twice is not an error."""
    target = get_user_model().objects.filter(pk=user_id).first() if str(user_id or "").isdigit() else None
    if target is None or not Membership.objects.filter(user=target, company=company).exists():
        return "User is not a team member."
    obj, created = ProductAccess.objects.get_or_create(product=product, user=target, company=company)
    if created:
        log_activity(
            company, "access_granted", f"{target.username} granted access to {product.name}", actor=actor,
            target_content_type="product_access", target_object_id=obj.pk,
            metadata={"product_id": product.pk, "user_id": target.pk},
        )
    return None


def revoke_access(product, target, actor, company):
    ProductAccess.objects.filter(product=product, user=target, company=company).delete()
    log_activity(
        company, "access_revoked", f"{target.username} access to {product.name} removed", actor=actor,
        target_content_type="product_access", target_object_id=None,
        metadata={"product_id": product.pk, "user_id": target.pk},
    )


def add_milestone(product, title, target_date, order, actor, company):
    ProductMilestone.objects.create(
        company=company, product=product, title=title, target_date=target_date, order=order,
        status=ProductMilestone.Status.UPCOMING,
    )
    log_activity(
        company, "milestone_added", f"Milestone '{title}' added to {product.name}",
        description=f"Target date {target_date:%b %d, %Y}", actor=actor,
        metadata={"product_id": product.pk, "title": title, "target_date": target_date.isoformat()},
    )


def toggle_milestone(milestone, actor, company):
    """Advance upcoming → in progress → completed; a completed one goes back to upcoming."""
    S = ProductMilestone.Status
    before = milestone.status
    if milestone.status == S.UPCOMING:
        milestone.status = S.IN_PROGRESS
    elif milestone.status in (S.IN_PROGRESS, S.OVERDUE):
        milestone.status, milestone.completed_at = S.COMPLETED, timezone.now()
    else:
        milestone.status, milestone.completed_at = S.UPCOMING, None
    milestone.save()
    log_activity(
        company, "milestone_toggled", f"Milestone '{milestone.title}' is now {milestone.get_status_display().lower()}",
        description=f"{S(before).label} → {milestone.get_status_display()}", actor=actor,
        metadata={"product_id": milestone.product_id, "from": before, "to": milestone.status},
    )


def delete_milestone(milestone, actor, company):
    product, title = milestone.product, milestone.title
    milestone.delete()
    log_activity(
        company, "milestone_deleted", f"Milestone \"{title}\" removed from {product.name}", actor=actor,
        metadata={"product_id": product.pk, "title": title},
    )

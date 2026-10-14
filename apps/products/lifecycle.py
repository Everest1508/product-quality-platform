"""A project's life: nine phases, who may move it, and the append-only log of everything that happens.

Every way of changing a project's stage goes through `move_stage`, so the board, the journey view and the
project page all log, notify and skip unused phases the same way. Nothing here edits a log entry.
"""

import re
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Membership
from apps.products.models import CrunchItem, PhasePlan, PodMember, ProductAccess, ProjectLogEntry

STAGES = [
    ("creation", "Creation"), ("fe", "FE"), ("be", "BE"), ("connection", "Connection"),
    ("deploy", "Deploy"), ("testing", "Testing"), ("uat", "UAT"), ("live", "Live"), ("close", "Close"),
]
KEYS = [k for k, _ in STAGES]
LABELS = dict(STAGES)
PRESETS = {
    "full": KEYS,
    "frontend": ["creation", "fe", "deploy", "testing", "uat", "live", "close"],
    "backend": ["creation", "be", "deploy", "testing", "uat", "live", "close"],
    "maintenance": ["creation", "be", "testing", "deploy", "live", "close"],
}
WRITE_KINDS = ("update", "blocker", "decision", "correction")
ADMIN_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)
_MENTION = re.compile(r"(?<![\w@.+-])@([\w.+-]{1,150})")


class LifecycleError(ValueError):
    """The action is not allowed or the input is not valid. The message is meant for the person."""


# ---- reading -------------------------------------------------------------------------------------------

def enabled_phases(product):
    chosen = [k for k in KEYS if k in (product.phases or [])]
    return chosen or list(KEYS)


def current_stage(product):
    return product.stage if product.stage in LABELS else "creation"


def entered_at(product):
    return product.stage_changed_at or product.created_at


def days_in_stage(product, now=None):
    return max(0, ((now or timezone.now()) - entered_at(product)).days)


def next_stage(product):
    """The next phase this project uses after its current one, or None at the end."""
    here = KEYS.index(current_stage(product))
    return next((k for k in enabled_phases(product) if KEYS.index(k) > here), None)


def pod_users(product):
    """The lead first, then everyone else on the Pod."""
    User = get_user_model()
    ids = list(product.pod_members.values_list("user_id", flat=True))
    if product.lead_id and product.lead_id not in ids:
        ids.insert(0, product.lead_id)
    elif product.lead_id:
        ids.remove(product.lead_id)
        ids.insert(0, product.lead_id)
    users = {u.pk: u for u in User.objects.filter(pk__in=ids)}
    return [users[i] for i in ids if i in users]


def is_pod(user, product):
    return bool(user and user.pk and (user.pk == product.lead_id or product.pod_members.filter(user=user).exists()))


def can_work(user, product, role):
    """May this person log updates and move the project: the Pod, the lead, owners and admins."""
    return role in ADMIN_ROLES or is_pod(user, product)


def history(product, now=None):
    """The phases the project has been through, each with when it was entered and left."""
    now = now or timezone.now()
    moves = list(product.log_entries.filter(kind="stage").order_by("created_at", "id"))
    first = moves[0].from_stage if moves and moves[0].from_stage in LABELS else current_stage(product)
    segments, stage, since = [], first if moves else current_stage(product), product.created_at
    for m in moves:
        segments.append({"stage": stage, "start": since, "end": m.created_at})
        stage, since = m.to_stage, m.created_at
    segments.append({"stage": stage, "start": since, "end": None})
    for seg in segments:
        seg["days"] = max(0, ((seg["end"] or now) - seg["start"]).days)
        seg["label"] = LABELS.get(seg["stage"], seg["stage"])
    return segments


# ---- people to tell ------------------------------------------------------------------------------------

def _mentioned(body, product):
    names = [n.rstrip(".").lower() for n in _MENTION.findall(body or "")]
    if not names:
        return []
    pool = {u.username.lower(): u for u in pod_users(product)}
    seen, out = set(), []
    for n in names:
        if n in pool and n not in seen:
            seen.add(n)
            out.append(pool[n])
    return out


def _tell(product, actor, title, body, mentioned=()):
    from apps.notifications import service
    from apps.notifications.models import Notification

    url = reverse("products:project_lifecycle", kwargs={"pk": product.pk})
    named = {u.pk for u in mentioned}
    for user in mentioned:
        service.notify(user=user, company=product.company, kind=Notification.Kind.MENTION,
                       title=f"{actor_name(actor)} mentioned you on {product.name}", body=body, url=url, actor=actor)
    for user in pod_users(product):
        if user.pk not in named:
            service.notify(user=user, company=product.company, kind=Notification.Kind.PROJECT,
                           title=title, body=body, url=url, actor=actor)


def actor_name(user):
    return (user.get_full_name() or user.username) if user else "Someone"


def _log(product, user, kind, body="", **extra):
    entry = ProjectLogEntry.objects.create(company=product.company, product=product, kind=kind, author=user, body=body, **extra)
    return entry


# ---- writing -------------------------------------------------------------------------------------------

def move_stage(product, to_stage, reason, user, role):
    """Move the project to another phase. A reason is required, and it is the log entry's text."""
    if not can_work(user, product, role):
        raise LifecycleError("Only the project lead, the Pod, owners and admins can move this project.")
    reason = (reason or "").strip()
    if not reason:
        raise LifecycleError("Say why you are moving this project.")
    if to_stage not in LABELS:
        raise LifecycleError("That is not a phase.")
    here = current_stage(product)
    if to_stage == here:
        raise LifecycleError(f"It is already in {LABELS[here]}.")
    if to_stage not in enabled_phases(product):
        raise LifecycleError(f"{LABELS[to_stage]} is not part of this project.")
    a, b = KEYS.index(here), KEYS.index(to_stage)
    lo, hi = sorted((a, b))
    skipped = [LABELS[k] for k in KEYS[lo + 1:hi] if k not in enabled_phases(product)]
    spent = days_in_stage(product)
    mentioned = _mentioned(reason, product)
    with transaction.atomic():
        product.stage, product.stage_changed_at = to_stage, timezone.now()
        product.save(update_fields=["stage", "stage_changed_at", "updated_at"])
        entry = _log(product, user, "stage", reason, from_stage=here, to_stage=to_stage,
                     meta={"days_in_from": spent, "back": b < a, "skipped": skipped})
        entry.mentions.set(mentioned)
    from apps.dashboards.service import log_activity

    log_activity(product.company, "project_stage", f"{product.name}: {LABELS[here]} to {LABELS[to_stage]}",
                 description=reason[:200], actor=user, target_content_type="product", target_object_id=product.pk,
                 metadata={"product_id": product.pk, "from": here, "to": to_stage})
    verb = "sent back to" if b < a else "moved to"
    _tell(product, user, f"{product.name} {verb} {LABELS[to_stage]}", f"{actor_name(user)}: {reason}", mentioned)
    return entry


def add_entry(product, user, role, kind, body):
    if not can_work(user, product, role):
        raise LifecycleError("Only the project lead, the Pod, owners and admins can add to this log.")
    body = (body or "").strip()
    if not body:
        raise LifecycleError("Write something first.")
    if kind not in WRITE_KINDS:
        kind = "update"
    mentioned = _mentioned(body, product)
    with transaction.atomic():
        entry = _log(product, user, kind, body)
        entry.mentions.set(mentioned)
    label = ProjectLogEntry.Kind(kind).label
    _tell(product, user, f"{label} on {product.name}", f"{actor_name(user)}: {body}", mentioned)
    return entry


def _ensure_access(product, users):
    for u in users:
        ProductAccess.objects.get_or_create(product=product, user=u, defaults={"company": product.company})


def set_team(product, lead, members, user):
    """Set the lead and the other Pod members. People added are given access to the product and told."""
    members = [m for m in members if m and (not lead or m.pk != lead.pk)]
    before = {u.pk for u in pod_users(product)}
    product.lead = lead
    product.save(update_fields=["lead", "updated_at"])
    keep = {m.pk for m in members}
    product.pod_members.exclude(user_id__in=keep).delete()
    for m in members:
        PodMember.objects.get_or_create(product=product, user=m, defaults={"company": product.company})
    _ensure_access(product, ([lead] if lead else []) + members)
    after = pod_users(product)
    added = [u for u in after if u.pk not in before]
    if {u.pk for u in after} != before:
        names = ", ".join(u.get_full_name() or u.username for u in after) or "nobody"
        _log(product, user, "setup", f"Pod: {names}", meta={"team": [u.pk for u in after]})
    from apps.notifications import service
    from apps.notifications.models import Notification

    for u in added:
        service.notify(user=u, company=product.company, kind=Notification.Kind.ASSIGNED,
                       title=f"You joined the Pod for {product.name}", url=reverse("products:project_lifecycle", kwargs={"pk": product.pk}), actor=user)


def _parse_date(value, label):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise LifecycleError(f"{label} is not a valid date.")


def save_plan(product, *, user, start=None, end=None, tech_stack=None, srs=None, phases=None, schedule=None):
    """Save the dates, phases, schedule, stack and SRS. `schedule` is {phase: {start, end, hours}}.

    Validates first and writes after, so a bad schedule changes nothing. Changes are logged in one entry.
    """
    start, end = _parse_date(start, "The start date"), _parse_date(end, "The end date")
    if start and end and end < start:
        raise LifecycleError("The end date is before the start date.")
    chosen = [k for k in KEYS if k in (phases if phases is not None else enabled_phases(product))]
    if not chosen:
        raise LifecycleError("Pick at least one phase.")
    if current_stage(product) not in chosen:
        raise LifecycleError(f"The project is in {LABELS[current_stage(product)]}, so that phase has to stay.")
    plans = {}
    for key, row in (schedule or {}).items():
        if key not in chosen:
            continue
        s, e = _parse_date(row.get("start"), f"{LABELS[key]} start"), _parse_date(row.get("end"), f"{LABELS[key]} end")
        hours = row.get("hours")
        try:
            hours = None if hours in (None, "") else round(float(hours), 1)
        except (TypeError, ValueError):
            raise LifecycleError(f"{LABELS[key]} hours is not a number.")
        if hours is not None and hours < 0:
            raise LifecycleError(f"{LABELS[key]} hours cannot be negative.")
        if s and e and e < s:
            raise LifecycleError(f"{LABELS[key]} ends before it starts.")
        for label, d in (("starts", s), ("ends", e)):
            if d and start and d < start:
                raise LifecycleError(f"{LABELS[key]} {label} before the project starts.")
            if d and end and d > end:
                raise LifecycleError(f"{LABELS[key]} {label} after the project ends.")
        if s or e or hours is not None:
            plans[key] = (s, e, hours)
    changes = []
    with transaction.atomic():
        if (start, end) != (product.start_date, product.end_date):
            changes.append("dates")
        if chosen != enabled_phases(product):
            changes.append("phases")
        product.start_date, product.end_date, product.phases = start, end, chosen
        if tech_stack is not None:
            product.tech_stack = [t.strip() for t in tech_stack if t and t.strip()][:30]
        if srs is not None and srs != product.srs:
            product.srs, product.srs_updated_at = srs, timezone.now()
            changes.append("SRS")
        product.save()
        have = {p.phase: p for p in product.phase_plans.all()}
        for key in list(have):
            if key not in plans:
                have[key].delete()
                if "schedule" not in changes:
                    changes.append("schedule")
        for key, (s, e, h) in plans.items():
            row = have.get(key)
            if not row or (row.start_date, row.end_date, row.planned_hours) != (s, e, None if h is None else Decimal(str(h))):
                if "schedule" not in changes:
                    changes.append("schedule")
            PhasePlan.objects.update_or_create(product=product, phase=key, defaults={"company": product.company, "start_date": s, "end_date": e, "planned_hours": h})
        if changes:
            _log(product, user, "schedule", "Updated " + ", ".join(changes) + ".", meta={"changed": changes})
    if changes:
        _tell(product, user, f"{product.name}: plan updated", f"{actor_name(user)} updated {', '.join(changes)}.")


def add_crunch(product, user, role, feature, due, reason=""):
    if not can_work(user, product, role):
        raise LifecycleError("Only the project lead, the Pod, owners and admins can add a Crunch item.")
    feature = (feature or "").strip()
    if not feature:
        raise LifecycleError("Name the feature.")
    due = _parse_date(due, "The due date")
    if not due:
        raise LifecycleError("A Crunch item needs a due date.")
    if product.end_date and due > product.end_date:
        raise LifecycleError("A Crunch date has to be before the project ends.")
    item = CrunchItem.objects.create(company=product.company, product=product, feature=feature[:200], due_date=due,
                                     reason=(reason or "").strip()[:300], created_by=user)
    _log(product, user, "crunch", f"Crunch: {feature} by {due:%d %b %Y}" + (f". {reason.strip()}" if reason and reason.strip() else ""),
         meta={"crunch": item.pk, "due": due.isoformat()})
    _tell(product, user, f"Crunch on {product.name}: {feature}", f"Due {due:%d %b %Y}. {actor_name(user)}")
    return item


def finish_crunch(item, user, role):
    product = item.product
    if not can_work(user, product, role):
        raise LifecycleError("Only the project lead, the Pod, owners and admins can do that.")
    if item.done:
        return item
    item.done, item.done_at = True, timezone.now()
    item.save(update_fields=["done", "done_at"])
    _log(product, user, "crunch", f"Crunch done: {item.feature}", meta={"crunch": item.pk, "done": True})
    _tell(product, user, f"Crunch done on {product.name}", f"{item.feature}. {actor_name(user)}")
    return item


def crunch_state(item, today=None):
    today = today or timezone.localdate()
    if item.done:
        return "done"
    if item.due_date < today:
        return "late"
    return "soon" if (item.due_date - today).days <= 3 else "open"

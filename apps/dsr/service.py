from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.dsr.models import DSREntry


def is_privileged(user, company):
    """Owners and admins: the people who may fix a closed day or read a colleague's sheet."""
    from apps.accounts.models import Membership

    membership = Membership.objects.filter(user=user, company=company).first()
    return bool(membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN))


def submission_window(day, is_privileged=False):
    """Whether a DSR day still accepts writes, and why not when it doesn't.

    A DSR day is submitted on the day itself, so it closes when the local
    calendar rolls over: at 23:59 local `today == day` and the sheet is still
    open, and at 00:00 the same sheet becomes a past day. That is the
    "submit by 11:59pm" boundary -- it is derived from the local date rather
    than a stored cutoff, so it cannot drift out of step with the timezone.

    Past days stay readable but read-only, so an earlier sheet can be checked
    and not rewritten. Owners and admins are the override for a forgotten or
    mistyped entry. Future days are closed to *everyone*: hours cannot be
    worked yet, and there is no business reason for an admin to pre-log them,
    so granting an override there would only let bad data in.

    Returns ``(can_submit, reason)``; ``reason`` is user-facing copy.
    """
    today = timezone.localdate()
    if day > today:
        return False, "That day has not happened yet. You can only log work up to today."
    if day < today and not is_privileged:
        return False, "This day is closed. It stays readable, but only today can be edited."
    return True, ""


def auto_log_ticket_dsr(ticket, actor=None):
    """Automatically log or update a DSR entry when a ticket is completed/resolved."""
    if ticket.status not in ["resolved", "closed"]:
        return

    now = timezone.now()
    log_date = timezone.localdate(now)

    start_time = ticket.created_at
    # The entry keeps the real created and completed moments, but the hours it claims for this day can never be more than
    # a working day: a ticket that sat open for weeks did not take weeks of someone's time.
    from apps.attendance.service import shift_for

    day_hours = Decimal(shift_for(ticket.company).worked_minutes_per_day) / Decimal(60)
    elapsed_hours = Decimal(str(max(0, (now - start_time).total_seconds()))) / Decimal(3600)
    day_hours = day_hours or Decimal("8")
    # A ticket open longer than a working day says how long it was open but claims no time: the person enters what they
    # worked on it, and only that counts towards the DSR.
    long_ticket = elapsed_hours > day_hours

    target_users = list(ticket.assignees.all())
    if not target_users:
        if actor:
            target_users = [actor]
        elif ticket.created_by:
            target_users = [ticket.created_by]

    category = DSREntry.Category.BUG_FIX if ticket.ticket_type == "bug" else DSREntry.Category.TICKET

    task_name = f"{ticket.key}: {ticket.title}"
    if ticket.product:
        task_name = f"[{ticket.product.name}] {task_name}"

    for user in target_users:
        existing = DSREntry.objects.filter(company=ticket.company, user=user, ticket=ticket, date=log_date).first()
        if long_ticket:
            hours_spent = existing.hours_spent if existing else Decimal("0.00")  # keep time the person already entered
        else:
            hours_spent = max(Decimal("0.25"), elapsed_hours).quantize(Decimal("0.01"))
        DSREntry.objects.update_or_create(
            company=ticket.company,
            user=user,
            ticket=ticket,
            date=log_date,
            defaults={
                "product": ticket.product,
                "task_name": task_name,
                "category": category,
                "created_time": start_time,
                "completed_time": now,
                "elapsed_hours": elapsed_hours.quantize(Decimal("0.01")),
                "hours_spent": hours_spent,
                "status": DSREntry.Status.COMPLETED,
                "is_auto_logged": True,
            },
        )


# --- Suggestions from the day's work ----------------------------------------

_TOUCH_EVENTS = ("ticket_created", "ticket_status_changed", "ticket_commented", "ticket_assigned")


def _quarter_hours(start, end):
    """The span between two moments as hours in quarters, kept within 0.5 to 4.

    A guess to prefill the box, never a record. Someone who touched a ticket at
    9:05 and again at 9:40 probably did not work eight hours on it, and one who
    touched it once has nothing to measure, so that case gets a flat hour.
    """
    minutes = (end - start).total_seconds() / 60
    if minutes < 15:
        return Decimal("1.00")
    quarters = round(minutes / 15)
    return Decimal(str(min(Decimal("4"), max(Decimal("0.5"), Decimal(quarters) / 4)))).quantize(Decimal("0.01"))


def suggestions(company, user, day, limit=8):
    """Tickets this person worked on that day that are not in their DSR yet.

    Built from what they did (the activity log) plus tickets assigned to them and
    still in progress. Scoped with `accessible_tickets`, so a suggestion can never
    name a ticket from a product they cannot open. Tickets already logged for the
    day, by hand or automatically, are left out.
    """
    from datetime import datetime, time

    from apps.dashboards.models import ActivityLog
    from apps.products.access import accessible_tickets

    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    logs = ActivityLog.objects.filter(
        company=company,
        actor=user,
        created_at__gte=start,
        created_at__lt=end,
        target_content_type="ticket",
        event_type__in=_TOUCH_EVENTS,
    ).order_by("created_at")
    touched = {}
    for log in logs:
        if log.target_object_id:
            touched.setdefault(log.target_object_id, []).append(log)

    visible = accessible_tickets(user, company)
    in_progress = set(
        visible.filter(assignees=user, status__in=["in_progress", "testing"]).values_list("pk", flat=True)
    )
    logged = set(
        DSREntry.objects.filter(company=company, user=user, date=day, ticket__isnull=False).values_list(
            "ticket_id", flat=True
        )
    )
    ids = (set(touched) | in_progress) - logged
    tickets = {t.pk: t for t in visible.filter(pk__in=ids).select_related("product")}

    rows = []
    for pk, ticket in tickets.items():
        events = touched.get(pk, [])
        did = []
        status_changes = [e for e in events if e.event_type == "ticket_status_changed"]
        if status_changes:
            to = (status_changes[-1].metadata or {}).get("to") or ticket.status
            did.append("resolved it" if to in ("resolved", "closed") else f"moved it to {to.replace('_', ' ')}")
        if any(e.event_type == "ticket_commented" for e in events):
            did.append("commented")
        if any(e.event_type == "ticket_created" for e in events):
            did.append("created it")
        if any(e.event_type == "ticket_assigned" for e in events):
            did.append("changed who it is assigned to")
        if not did:
            did.append("assigned to you, in progress")
        rows.append(
            {
                "ticket": ticket,
                "number": ticket.pk,
                "key": ticket.key,
                "title": ticket.title,
                "product": ticket.product.name if ticket.product else "",
                "did": ", ".join(did).capitalize() if len(did) == 1 else ", ".join(did[:-1]).capitalize() + " and " + did[-1],
                "touched": bool(events),
                "hours": _quarter_hours(events[0].created_at, events[-1].created_at) if len(events) > 1 else Decimal("1.00"),
                "category": (
                    DSREntry.Category.BUG_FIX if ticket.ticket_type == "bug"
                    else DSREntry.Category.FEATURE if ticket.ticket_type == "feature"
                    else DSREntry.Category.TICKET
                ),
                "status": (
                    DSREntry.Status.COMPLETED if ticket.status in ("resolved", "closed") else DSREntry.Status.IN_PROGRESS
                ),
                "last": events[-1].created_at if events else None,
                "events": [e.created_at for e in events],
            }
        )
    rows.sort(key=lambda r: (not r["touched"], -(r["last"].timestamp() if r["last"] else 0), r["number"]))
    return rows[:limit]


def add_all_suggested(company, actor, target_user, day):
    """Log every suggested ticket at its suggested hours. Returns (entries, message)."""
    from apps.dsr.duration import format_hm

    entries = []
    for row in suggestions(company, target_user, day, limit=50):
        entry, _ = add_suggested(company, actor, target_user, day, row["number"], str(row["hours"]))
        if entry is not None:
            entries.append(entry)
    if not entries:
        return [], "There is nothing to add."
    total = sum((e.hours_spent for e in entries), Decimal("0.00"))
    return entries, f"Added {len(entries)} ticket{'s' if len(entries) != 1 else ''} to your DSR ({format_hm(total)} in all)."


# ── Writes, shared by the JSON API. Access and the day's window are checked by the caller. ──

def add_entry(company, actor, target_user, day, data, products):
    """A manual row. Returns (entry, form); entry is None when the form is invalid."""
    from apps.dashboards.service import log_activity
    from apps.dsr.forms import DSREntryForm

    form = DSREntryForm(data, products=products)
    if not form.is_valid():
        return None, form
    entry = form.save(commit=False)
    entry.company, entry.user, entry.date, entry.is_auto_logged = company, target_user, day, False
    entry.save()
    log_activity(
        company, "dsr_entry_added", f"{entry.task_name} logged",
        description=f"{entry.date} · {entry.category} · {entry.hours_spent}h", actor=actor,
        metadata={"user_id": entry.user_id, "date": entry.date.isoformat(), "product_id": entry.product_id},
    )
    return entry, form


def update_entry(company, actor, entry, data, products):
    """Edit a row. Fields that are not sent keep their value (a ticket's row keeps its own product).
    Returns (entry, form); entry is None when the form is invalid and nothing was saved."""
    from apps.dashboards.service import log_activity
    from apps.dsr.forms import DSREntryForm

    merged = {
        "task_name": data.get("task_name", entry.task_name),
        "product": data.get("product", entry.product_id or ""),
        "category": data.get("category", entry.category),
        "hours_spent": data.get("hours_spent", entry.hours_spent),
        "status": data.get("status", entry.status),
        "notes": data.get("notes", entry.notes),
    }
    form = DSREntryForm(merged, instance=entry, products=products)
    if not form.is_valid():
        entry.refresh_from_db()
        return None, form
    form.save()
    log_activity(
        company, "dsr_entry_updated", f"{entry.task_name} updated on the DSR",
        description=f"{entry.date} · {entry.hours_spent}h · {entry.get_status_display()}", actor=actor,
        metadata={"user_id": entry.user_id, "date": entry.date.isoformat(), "product_id": entry.product_id},
    )
    return entry, form


def delete_entry(company, actor, entry):
    from apps.dashboards.service import log_activity

    day, owner, name, hours = entry.date, entry.user, entry.task_name, entry.hours_spent
    entry.delete()
    log_activity(
        company, "dsr_entry_deleted", f"\"{name}\" removed from the DSR", description=f"{day} · {hours}h", actor=actor,
        metadata={"user_id": owner.pk, "date": day.isoformat()},
    )
    return name


def add_suggested(company, actor, target_user, day, ticket_id, hours):
    """Log one suggested ticket with the hours the person confirmed.
    Returns (entry, error); only a ticket the sheet actually suggests can be added."""
    from apps.dashboards.service import log_activity
    from apps.dsr.duration import MESSAGE, format_hm, parse_hours

    try:
        ticket_id = int(ticket_id)
        hours = parse_hours(hours if hours is not None else "")
    except (TypeError, ValueError):
        return None, MESSAGE + "."
    if hours is None or hours <= 0 or hours > 24:
        return None, "Time must be more than 0 and at most 24 hours."
    match = next((r for r in suggestions(company, target_user, day, limit=50) if r["number"] == ticket_id), None)
    if match is None:
        return None, "That ticket is not in your suggestions for this day."
    ticket = match["ticket"]
    entry = DSREntry.objects.create(
        company=company, user=target_user, date=day, ticket=ticket, product=ticket.product,
        task_name=f"{ticket.key} {ticket.title}"[:255], category=match["category"],
        hours_spent=hours.quantize(Decimal("0.01")), status=match["status"], is_auto_logged=False,
    )
    log_activity(
        company, "dsr_entry_added", f"{entry.task_name} logged",
        description=f"{entry.date} · {entry.category} · {entry.hours_spent}h", actor=actor,
        metadata={"user_id": entry.user_id, "date": entry.date.isoformat(), "product_id": entry.product_id},
    )
    return entry, f"Added {ticket.key} with {format_hm(hours)}."


def _fmt_hm(hours):
    from apps.dsr.duration import format_hm

    return format_hm(hours)


def elapsed_label(e):
    """How long the ticket was open: "3h 20m", or "11d 1h" past two days. Empty when it is not known."""
    if e.elapsed_hours is not None:
        minutes = int(e.elapsed_hours * 60)
    elif e.created_time and e.completed_time:
        minutes = max(0, int((e.completed_time - e.created_time).total_seconds() // 60))
    else:
        return ""
    days, rest = divmod(minutes, 1440)
    return f"{days}d {rest // 60}h" if days >= 2 else _fmt_hm(Decimal(minutes) / 60)


def pending_time_entry(company, user, ticket):
    """Today's auto-logged row for this ticket and person if it is waiting for the time they worked, else None."""
    entry = DSREntry.objects.filter(company=company, user=user, ticket=ticket, date=timezone.localdate()).first()
    return entry if entry is not None and entry.needs_time else None


def needs_time_notice(company, user, ticket):
    """The sentence to show a person who has just resolved a long-open ticket, or "" when there is nothing to ask for."""
    waiting = pending_time_entry(company, user, ticket)
    if waiting is None:
        return ""
    return f"{ticket.key} was open for {elapsed_label(waiting)}. Add the time you worked on it today in your DSR."

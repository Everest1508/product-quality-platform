"""CardSnap cloud backup: validation and the batched write path. Text only, never photos.

Load: an upload of up to 200 cards costs a fixed handful of queries (one SELECT of the rows it touches, one
COUNT, one bulk insert, one bulk update), never one query per card. Restores are keyset-paged and read raw rows.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.appauth.models import AppCard
from apps.appauth.service import AuthError

MAX_BATCH = 200
MAX_CARDS = 5000
MAX_LIST = 20
MAX_ITEM = 100
MAX_SCANS = 10000
MAX_BODY = 2 * 1024 * 1024
CLOCK_SLACK = timedelta(minutes=5)

TEXT = {"name": 255, "company": 255, "designation": 255, "website": 500, "address": 1000, "notes": 5000,
        "linkedin_url": 500, "twitter_handle": 100, "exhibition_name": 255}
LISTS = ("phones", "emails", "tags")
FIELDS = [*TEXT, *LISTS, "is_favorite", "scan_count", "created_at_client", "updated_at_client"]
OUT = ["client_id", *FIELDS]  # Anything else a client sends (photos included) is dropped, never stored.


def bad(i, why):
    return AuthError("invalid_card", f"Card {i + 1}: {why}.", 400)


def _when(v, now, i, field):
    dt = parse_datetime(v) if isinstance(v, str) else None
    if dt is None or timezone.is_naive(dt):
        raise bad(i, f"{field} must be an ISO date-time with a time zone")
    return min(dt, now + CLOCK_SLACK)  # a wrong phone clock must not win every later sync


def clean(raw, i, now):
    """One card from the request, validated and trimmed to what we store."""
    if not isinstance(raw, dict):
        raise bad(i, "must be an object")
    try:
        out = {"client_id": uuid.UUID(str(raw.get("client_id")))}
    except ValueError:
        raise bad(i, "client_id must be a UUID")
    for f, cap in TEXT.items():
        v = raw.get(f) or ""
        if not isinstance(v, str) or len(v) > cap:
            raise bad(i, f"{f} must be text of at most {cap} characters")
        out[f] = v
    for f in LISTS:
        v = raw.get(f) or []
        if not isinstance(v, list) or len(v) > MAX_LIST or any(not isinstance(x, str) or len(x) > MAX_ITEM for x in v):
            raise bad(i, f"{f} must be a list of at most {MAX_LIST} items of at most {MAX_ITEM} characters")
        out[f] = v
    out["is_favorite"] = raw.get("is_favorite") is True
    n = raw.get("scan_count")
    if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= MAX_SCANS:
        out["scan_count"] = n  # anything else is left out, so a stored value stays and a new card gets 1
    out["updated_at_client"] = _when(raw.get("updated_at_client"), now, i, "updated_at_client")
    out["created_at_client"] = (_when(raw["created_at_client"], now, i, "created_at_client")
                                if raw.get("created_at_client") else out["updated_at_client"])
    return out


def require_backup(user):
    if not user.cloud_backup_enabled:
        raise AuthError("backup_off", "Cloud backup is turned off.", 403)
    if (user.cloud_consent_version or 0) < settings.CARDSNAP_CONSENT_VERSION:
        raise AuthError("consent_required", "Please review and accept the updated backup terms.", 403)


def upsert(user, raw_cards):
    """Last write wins on `updated_at_client`; a stale copy is ignored. All or nothing. Returns rows saved."""
    if not isinstance(raw_cards, list) or len(raw_cards) > MAX_BATCH:
        raise AuthError("invalid_request", f"Send a list of at most {MAX_BATCH} cards.", 400)
    now = timezone.now()
    incoming = {}
    for i, raw in enumerate(raw_cards):  # same card twice in one batch: the newer copy wins
        c = clean(raw, i, now)
        if c["client_id"] not in incoming or c["updated_at_client"] >= incoming[c["client_id"]]["updated_at_client"]:
            incoming[c["client_id"]] = c
    if not incoming:
        return 0
    with transaction.atomic():
        have = {r.client_id: r for r in AppCard.objects.filter(user=user, client_id__in=incoming)}
        new = [c for cid, c in incoming.items() if cid not in have]
        revived = sum(1 for r in have.values() if r.deletion_requested_at)
        if new or revived:
            live = AppCard.objects.live().filter(user=user).count()
            if live + len(new) + revived > MAX_CARDS:
                raise AuthError("limit_reached", f"You can back up at most {MAX_CARDS} cards.", 409)
        changed = []
        for cid, row in have.items():
            c = incoming[cid]
            # A pending-deletion row that is uploaded again is wanted again, whatever its age.
            if c["updated_at_client"] > row.updated_at_client or row.deletion_requested_at:
                for f in FIELDS:
                    if f in c:
                        setattr(row, f, c[f])
                row.deletion_requested_at, row.updated_at = None, now
                changed.append(row)
        AppCard.objects.bulk_create([AppCard(user=user, **c) for c in new])
        AppCard.objects.bulk_update(changed, [*FIELDS, "deletion_requested_at", "updated_at"], batch_size=100)
    return len(new) + len(changed)


def page(user, after=None, since=None, limit=500):
    """Keyset page over the person's own live cards, as plain dicts (no model objects built)."""
    qs = AppCard.objects.live().filter(user=user).order_by("id")
    if since:
        qs = qs.filter(updated_at__gt=since)
    if after:
        qs = qs.filter(id__gt=after)
    rows = list(qs.values("id", *OUT)[:limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    for r in rows:
        r["client_id"] = str(r["client_id"])
        for f in ("created_at_client", "updated_at_client"):
            r[f] = r[f].isoformat()
    cursor = str(rows[-1]["id"]) if more else None
    for r in rows:
        del r["id"]
    return rows, cursor


def request_erasure(user):
    """Hide every card now; purge_cardsnap_cards removes them after the retention period."""
    now = timezone.now()
    AppCard.objects.live().filter(user=user).update(deletion_requested_at=now)
    return (now + timedelta(days=settings.CARDSNAP_RETENTION_DAYS)).date().isoformat()

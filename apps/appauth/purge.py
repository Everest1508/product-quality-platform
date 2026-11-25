"""Erasure of CardSnap data once its waiting time is over. Runs by itself inside the server (see core/asgi.py);
`manage.py purge_cardsnap_cards` runs the same code by hand. Safe to run any time, any number of times, from any worker:
it only deletes rows already past their date, in small chunks."""
import logging
import threading
import time
from datetime import timedelta

from django import db
from django.conf import settings
from django.utils import timezone

from apps.appauth.models import AppCard, AppCardAccessLog, ScanFeedback

log = logging.getLogger(__name__)
CHUNK = 1000
EVERY = 6 * 60 * 60  # seconds between runs; a deletion is at most this late past its date
FIRST_RUN_AFTER = 60

_started = False
_lock = threading.Lock()


def delete_in_chunks(qs):
    """Small deletes, so a big purge never holds the database for long."""
    total = 0
    while True:
        ids = list(qs.values_list("pk", flat=True)[:CHUNK])
        if not ids:
            return total
        total += qs.model.objects.filter(pk__in=ids).delete()[0]


def run_purge(now=None):
    """Delete cards whose erasure was requested more than CARDSNAP_RETENTION_DAYS ago, and old log and feedback rows.
    Returns (cards, access_log_rows, scan_feedback_rows)."""
    now = now or timezone.now()
    cards = delete_in_chunks(AppCard.objects.filter(
        deletion_requested_at__lt=now - timedelta(days=settings.CARDSNAP_RETENTION_DAYS)))
    logs = delete_in_chunks(AppCardAccessLog.objects.filter(
        created_at__lt=now - timedelta(days=settings.CARDSNAP_AUDIT_RETENTION_DAYS)))
    scans = delete_in_chunks(ScanFeedback.objects.filter(
        received_at__lt=now - timedelta(days=settings.SCAN_FEEDBACK_RETENTION_DAYS)))
    return cards, logs, scans


def _loop():
    time.sleep(FIRST_RUN_AFTER)
    while True:
        try:
            cards, logs, scans = run_purge()
            if cards or logs or scans:
                log.info("CardSnap purge removed %s cards, %s access-log rows, %s scan-feedback rows", cards, logs, scans)
        except Exception:  # never let a bad run end the loop; the next one tries again
            log.exception("CardSnap purge failed")
        finally:
            db.close_old_connections()
        time.sleep(EVERY)


def start_background_purge():
    """Start the once-per-few-hours purge in a daemon thread. Called from the ASGI entry point only, so tests,
    migrations and other management commands never start it. A second call in the same process does nothing."""
    global _started
    if not getattr(settings, "CARDSNAP_AUTO_PURGE", True):
        return False
    with _lock:
        if _started:
            return False
        _started = True
    threading.Thread(target=_loop, name="cardsnap-purge", daemon=True).start()
    return True

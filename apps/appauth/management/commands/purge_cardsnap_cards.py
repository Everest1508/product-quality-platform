from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.appauth.models import AppCard, AppCardAccessLog, ScanFeedback

CHUNK = 1000


def _delete_in_chunks(qs):
    """Small deletes, so a big purge never holds the database for long."""
    total = 0
    while True:
        ids = list(qs.values_list("pk", flat=True)[:CHUNK])
        if not ids:
            return total
        total += qs.model.objects.filter(pk__in=ids).delete()[0]


class Command(BaseCommand):
    help = ("Erase backed-up cards whose deletion was requested more than CARDSNAP_RETENTION_DAYS ago "
            "(default 30), staff-access log rows older than CARDSNAP_AUDIT_RETENTION_DAYS (default 365), and "
            "scan-feedback rows older than SCAN_FEEDBACK_RETENTION_DAYS (default 400). "
            "SCHEDULE THIS DAILY (cron or a systemd timer): until it runs, requested erasures are only hidden.")

    def handle(self, *args, **opts):
        now = timezone.now()
        cards = _delete_in_chunks(AppCard.objects.filter(
            deletion_requested_at__lt=now - timedelta(days=settings.CARDSNAP_RETENTION_DAYS)))
        logs = _delete_in_chunks(AppCardAccessLog.objects.filter(
            created_at__lt=now - timedelta(days=settings.CARDSNAP_AUDIT_RETENTION_DAYS)))
        scans = _delete_in_chunks(ScanFeedback.objects.filter(
            received_at__lt=now - timedelta(days=settings.SCAN_FEEDBACK_RETENTION_DAYS)))
        self.stdout.write(f"Purged {cards} cards, {logs} access-log rows and {scans} scan-feedback rows.")

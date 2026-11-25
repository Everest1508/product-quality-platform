from django.core.management.base import BaseCommand

from apps.appauth.purge import run_purge


class Command(BaseCommand):
    help = ("Erase backed-up cards whose deletion was requested more than CARDSNAP_RETENTION_DAYS ago (default 30), "
            "staff-access log rows older than CARDSNAP_AUDIT_RETENTION_DAYS (default 365) and scan-feedback rows older "
            "than SCAN_FEEDBACK_RETENTION_DAYS (default 400). The server already does this by itself every few hours; "
            "run this to do it right now.")

    def handle(self, *args, **opts):
        cards, logs, scans = run_purge()
        self.stdout.write(f"Purged {cards} cards, {logs} access-log rows and {scans} scan-feedback rows.")

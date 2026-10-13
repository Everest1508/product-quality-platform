from django.core.management.base import BaseCommand

from apps.accounts.models import Company
from apps.attendance import reminders


class Command(BaseCommand):
    help = "Remind people to check in (shortly after their shift starts) and out (after it ends). Run it from cron every 5-10 minutes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count what would be sent without sending.")

    def handle(self, *args, **options):
        total = sum(reminders.send(c, dry_run=options["dry_run"]) for c in Company.objects.all())
        self.stdout.write(f"{'Would send' if options['dry_run'] else 'Sent'} {total} reminder(s).")

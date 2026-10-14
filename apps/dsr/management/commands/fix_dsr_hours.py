from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.attendance.service import shift_for
from apps.dsr.models import DSREntry


class Command(BaseCommand):
    help = (
        "Stop auto-logged DSR rows from counting a whole open ticket as worked time. A row with more hours than one working day "
        "keeps those hours as its elapsed (open-for) time, which stays visible, and counts 0 until someone enters their real time."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")

    def handle(self, *args, **options):
        changed = 0
        caps = {}
        for entry in DSREntry.objects.filter(is_auto_logged=True, elapsed_hours__isnull=True).select_related("company"):
            cap = caps.setdefault(entry.company_id, (Decimal(shift_for(entry.company).worked_minutes_per_day) / Decimal(60)).quantize(Decimal("0.01")) or Decimal("8.00"))
            if entry.hours_spent > cap:
                self.stdout.write(f"{entry.pk} {entry.task_name[:50]}: open for {entry.hours_spent}h -> counts 0h, open-for time kept")
                if not options["dry_run"]:
                    entry.elapsed_hours = entry.hours_spent
                    entry.hours_spent = Decimal("0.00")
                    entry.save(update_fields=["elapsed_hours", "hours_spent", "updated_at"])
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"{changed} entr{'y' if changed == 1 else 'ies'} {'would stop' if options['dry_run'] else 'stopped'} counting towards the DSR."))

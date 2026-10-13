from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.attendance.service import shift_for
from apps.dsr.models import DSREntry


class Command(BaseCommand):
    help = "Cap auto-logged DSR entries at one working day (they used to log the whole time a ticket was open)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")

    def handle(self, *args, **options):
        changed = 0
        caps = {}
        for entry in DSREntry.objects.filter(is_auto_logged=True).select_related("company"):
            cap = caps.setdefault(entry.company_id, (Decimal(shift_for(entry.company).worked_minutes_per_day) / Decimal(60)).quantize(Decimal("0.01")) or Decimal("8.00"))
            if entry.hours_spent > cap:
                self.stdout.write(f"{entry.pk} {entry.task_name[:50]}: {entry.hours_spent}h -> {cap}h")
                if not options["dry_run"]:
                    entry.hours_spent = cap
                    entry.save(update_fields=["hours_spent", "updated_at"])
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"{changed} entr{'y' if changed == 1 else 'ies'} {'would be ' if options['dry_run'] else ''}capped."))

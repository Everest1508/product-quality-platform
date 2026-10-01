"""Find (and optionally repair) DecimalField values SQLite can no longer convert.

A single non-finite or over-long decimal takes down every page that reads its
table, because the failure is in the cursor's type converter, before the view
runs. This command is the only way to find such a row: the ORM cannot load it.

    python manage.py audit_decimals                  # report, changes nothing
    python manage.py audit_decimals --model payroll.Payslip
    python manage.py audit_decimals --fix --backup /tmp/decimals.json
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.core import decimals


class Command(BaseCommand):
    help = "Report DecimalField values that raise decimal.InvalidOperation on read."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            help="Limit to one model, e.g. payroll.Payslip.",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Overwrite every offending cell with --set (default 0).",
        )
        parser.add_argument(
            "--set",
            dest="replacement",
            default="0",
            help="Value to write with --fix. Default 0.",
        )
        parser.add_argument(
            "--backup",
            help="JSON file to dump the offending rows to before writing.",
        )
        parser.add_argument(
            "--database",
            default="default",
            help="Database alias. Default 'default'.",
        )

    def handle(self, *args, **options):
        using = options["database"]
        try:
            replacement = Decimal(options["replacement"])
        except InvalidOperation as exc:
            raise CommandError(f"--set must be a decimal number: {exc}")

        problems = decimals.scan(using=using, model_label=options["model"])

        if not problems:
            self.stdout.write(self.style.SUCCESS("No unreadable decimal values."))
            return

        self.stdout.write(
            self.style.ERROR(f"{len(problems)} unreadable decimal value(s):")
        )
        for problem in problems:
            self.stdout.write(
                f"  {problem['model']}.{problem['column']} pk={problem['pk']} "
                f"raw={problem['raw']} -- {problem['reason']}"
            )

        if not options["fix"]:
            self.stdout.write(
                "Re-run with --fix to overwrite these (add --backup to keep a copy)."
            )
            return

        if not replacement.is_finite():
            raise CommandError("--set must be finite; that is the problem being fixed.")

        if options["backup"]:
            path = decimals.dump_backup(problems, options["backup"])
            self.stdout.write(f"Backed up {len(problems)} row(s) to {path}")

        changed = decimals.repair(problems, using=using, replacement=replacement)
        self.stdout.write(
            self.style.SUCCESS(
                f"Repaired {len(changed)} cell(s), writing {replacement}. "
                "The rows are named above and in the backup; nothing else was touched."
            )
        )

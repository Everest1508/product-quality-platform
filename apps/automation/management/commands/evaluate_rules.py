from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.automation.models import AutoTicketLog, AutoTicketRule
from apps.ingestion.models import ErrorGroup


class Command(BaseCommand):
    help = "Evaluate auto-ticket rules and create tickets when thresholds are met."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be triggered without creating tickets.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        rules = AutoTicketRule.objects.filter(
            is_active=True,
            trigger_type=AutoTicketRule.TriggerType.ERROR_THRESHOLD,
        ).select_related("product", "assign_to")

        now = timezone.now()
        tickets_created = 0

        for rule in rules:
            window_start = now - timedelta(minutes=rule.window_minutes)

            qs = ErrorGroup.objects.filter(
                company=rule.company,
                first_seen__gte=window_start,
            )

            if rule.product:
                qs = qs.filter(product=rule.product)

            if rule.severity:
                qs = qs.filter(severity=rule.severity)

            matching_groups = []
            for eg in qs:
                if eg.occurrence_count >= rule.threshold_count:
                    matching_groups.append(eg)

            if not matching_groups:
                continue

            for eg in matching_groups:
                already_triggered = AutoTicketLog.objects.filter(
                    rule=rule,
                    error_group=eg,
                    created_at__gte=window_start,
                ).exists()
                if already_triggered:
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[DRY RUN] Would trigger rule '{rule.name}' "
                            f"for error group #{eg.pk} '{eg.title}' "
                            f"(count={eg.occurrence_count}, threshold={rule.threshold_count})"
                        )
                    )
                    continue

                ticket = None
                if rule.action == AutoTicketRule.ActionType.CREATE_TICKET:
                    from apps.tickets.models import Ticket
                    ticket = Ticket.objects.create(
                        company=rule.company,
                        product=eg.product,
                        title=f"[Auto] {eg.title}",
                        description=(
                            f"Auto-created by rule '{rule.name}'.\n\n"
                            f"Error group: #{eg.pk}\n"
                            f"Fingerprint: {eg.fingerprint}\n"
                            f"Occurrences: {eg.occurrence_count}\n"
                            f"Severity: {eg.severity}\n"
                            f"Window: {rule.window_minutes} minutes"
                        ),
                        ticket_type="bug",
                        priority=eg.severity if eg.severity in ("critical", "high", "medium", "low") else "medium",
                        source="auto",
                        assigned_to=rule.assign_to,
                        linked_error_group=eg,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created ticket #{ticket.pk} for error group #{eg.pk} "
                            f"(rule: {rule.name})"
                        )
                    )
                    tickets_created += 1

                AutoTicketLog.objects.create(
                    rule=rule,
                    company=rule.company,
                    error_group=eg,
                    ticket=ticket,
                    matched_count=eg.occurrence_count,
                    action_taken=rule.action,
                )

            rule.last_triggered_at = now
            rule.trigger_count += 1
            rule.save(update_fields=["last_triggered_at", "trigger_count"])

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done. {tickets_created} ticket(s) created."))

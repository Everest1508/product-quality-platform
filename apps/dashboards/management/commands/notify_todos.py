from django.core.management.base import BaseCommand

from apps.accounts.models import Membership
from apps.dashboards import todos


class Command(BaseCommand):
    help = "Send each person one bell/push a day about their overdue to-dos. Run it from cron, e.g. every morning."

    def handle(self, *args, **options):
        sent = 0
        for m in Membership.objects.select_related("user", "company"):
            if todos.notify_overdue(m.user, m.company):
                sent += 1
        self.stdout.write(f"Sent {sent} reminder(s).")

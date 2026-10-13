from datetime import timedelta
from decimal import Decimal
import re
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dsr.models import DSREntry
from apps.dsr.service import auto_log_ticket_dsr
from apps.tickets.models import Ticket

User = get_user_model()


class DSRSystemTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.owner = User.objects.create_user(username="owner", password="password")
        self.member = User.objects.create_user(username="member", password="password")

        Membership.objects.create(user=self.owner, company=self.company, role=Membership.Role.OWNER)
        Membership.objects.create(user=self.member, company=self.company, role=Membership.Role.DEVELOPER)

        self.ticket = Ticket.objects.create(
            company=self.company,
            title="Fix SSL certificate renewal",
            created_by=self.member,
            ticket_type="bug",
        )
        self.ticket.assignees.add(self.member)

    def test_auto_log_ticket_dsr(self):
        # Move ticket status to resolved
        self.ticket.transition_to("resolved", actor=self.member)

        # Check DSR entry created automatically
        entry = DSREntry.objects.filter(company=self.company, user=self.member, ticket=self.ticket).first()
        self.assertIsNotNone(entry)
        self.assertTrue(entry.is_auto_logged)
        self.assertIn("Fix SSL certificate renewal", entry.task_name)
        self.assertEqual(entry.status, "completed")
        self.assertGreater(entry.hours_spent, Decimal("0"))

    def test_a_long_open_ticket_cannot_break_the_dashboard(self):
        """A ticket open longer than 999.99h used to 500 the dashboard.

        `auto_log_ticket_dsr` writes `now - ticket.created_at` with no upper
        bound and no full_clean, and the field used to be max_digits=5. Any
        ticket open 42+ days therefore stored a value the decimal converter
        could not read back, and `_personal_dsr` raised InvalidOperation on
        every dashboard load for that user.
        """
        old = timezone.now() - timedelta(days=60)
        Ticket.objects.filter(pk=self.ticket.pk).update(created_at=old)
        self.ticket.refresh_from_db()

        self.ticket.transition_to("resolved", actor=self.member)

        entry = DSREntry.objects.get(ticket=self.ticket)
        # 60 days == 1440h, which the old 5-digit field could not store.
        self.assertGreater(entry.hours_spent, Decimal("999.99"))
        # And it must survive the read-back that used to explode.
        self.assertEqual(DSREntry.objects.get(pk=entry.pk).hours_spent, entry.hours_spent)

        self.client.login(username="member", password="password")
        response = self.client.get("/ui-api/v1/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_hours_survive_a_wide_round_trip(self):
        """99999h was the widest figure anyone actually asked for."""
        self.client.login(username="member", password="password")
        DSREntry.objects.create(
            company=self.company,
            user=self.member,
            date=timezone.localdate(),
            task_name="Long-running migration",
            hours_spent=Decimal("99999.99"),
        )
        stored = DSREntry.objects.get(task_name="Long-running migration")
        self.assertEqual(stored.hours_spent, Decimal("99999.99"))
        response = self.client.get("/ui-api/v1/dashboard/")
        self.assertEqual(response.status_code, 200)

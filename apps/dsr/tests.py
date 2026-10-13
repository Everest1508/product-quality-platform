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

    def test_a_long_open_ticket_logs_at_most_one_working_day_but_keeps_both_moments(self):
        """A ticket that sat open for 60 days used to log 1440 hours. It now logs one working day and keeps the
        created and completed times, so the DSR shows when it started and finished."""
        old = timezone.now() - timedelta(days=60)
        Ticket.objects.filter(pk=self.ticket.pk).update(created_at=old)
        self.ticket.refresh_from_db()

        self.ticket.transition_to("resolved", actor=self.member)

        entry = DSREntry.objects.get(ticket=self.ticket)
        self.assertEqual(entry.hours_spent, Decimal("7.50"))  # the default shift, 10:00-18:30 less a 60 minute break
        self.assertEqual(entry.created_time, old)
        self.assertIsNotNone(entry.completed_time)
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


class FixDsrHoursCommandTest(TestCase):
    def test_it_caps_only_inflated_auto_entries(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.accounts.models import Company

        company = Company.objects.create(name="Co", slug="co")
        user = get_user_model().objects.create_user("u", "u@t.local", "x")
        big = DSREntry.objects.create(company=company, user=user, task_name="auto big", hours_spent=Decimal("1440.00"), is_auto_logged=True)
        small = DSREntry.objects.create(company=company, user=user, task_name="auto small", hours_spent=Decimal("2.00"), is_auto_logged=True)
        manual = DSREntry.objects.create(company=company, user=user, task_name="manual", hours_spent=Decimal("20.00"), is_auto_logged=False)
        call_command("fix_dsr_hours", "--dry-run", stdout=StringIO())
        big.refresh_from_db()
        self.assertEqual(big.hours_spent, Decimal("1440.00"))
        call_command("fix_dsr_hours", stdout=StringIO())
        for e in (big, small, manual):
            e.refresh_from_db()
        self.assertEqual((big.hours_spent, small.hours_spent, manual.hours_spent), (Decimal("7.50"), Decimal("2.00"), Decimal("20.00")))

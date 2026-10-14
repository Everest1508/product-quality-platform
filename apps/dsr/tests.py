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

    def test_a_long_open_ticket_shows_how_long_it_was_open_but_counts_no_time_until_the_person_enters_theirs(self):
        """A ticket open for 60 days used to log 1440 hours. It now records that it was open that long (shown, never
        counted) and claims 0 hours until the person types in the time they worked on it."""
        old = timezone.now() - timedelta(days=60)
        Ticket.objects.filter(pk=self.ticket.pk).update(created_at=old)
        self.ticket.refresh_from_db()

        self.ticket.transition_to("resolved", actor=self.member)

        entry = DSREntry.objects.get(ticket=self.ticket)
        self.assertEqual(entry.hours_spent, Decimal("0.00"))
        self.assertGreaterEqual(entry.elapsed_hours, Decimal("1439.99"))
        self.assertTrue(entry.needs_time)
        self.assertEqual(entry.created_time, old)
        self.assertIsNotNone(entry.completed_time)

        # Entering real time counts it, and resolving again does not wipe what was entered.
        DSREntry.objects.filter(pk=entry.pk).update(hours_spent=Decimal("2.50"))
        self.ticket.transition_to("resolved", actor=self.member)
        entry.refresh_from_db()
        self.assertEqual(entry.hours_spent, Decimal("2.50"))
        self.assertFalse(entry.needs_time)

        self.client.login(username="member", password="password")
        self.assertEqual(self.client.get("/ui-api/v1/dashboard/").status_code, 200)

    def test_a_short_ticket_still_logs_its_elapsed_time(self):
        self.ticket.transition_to("resolved", actor=self.member)
        entry = DSREntry.objects.get(ticket=self.ticket)
        self.assertGreater(entry.hours_spent, Decimal("0"))
        self.assertFalse(entry.needs_time)

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
    def test_it_keeps_the_open_for_time_and_stops_inflated_auto_entries_counting(self):
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
        self.assertEqual((big.hours_spent, small.hours_spent, manual.hours_spent), (Decimal("0.00"), Decimal("2.00"), Decimal("20.00")))
        self.assertEqual(big.elapsed_hours, Decimal("1440.00"))  # how long it took is kept, it just no longer counts
        self.assertIsNone(small.elapsed_hours)
        call_command("fix_dsr_hours", stdout=StringIO())  # running it again changes nothing
        big.refresh_from_db()
        self.assertEqual((big.hours_spent, big.elapsed_hours), (Decimal("0.00"), Decimal("1440.00")))

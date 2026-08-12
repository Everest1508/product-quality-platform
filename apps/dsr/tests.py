from datetime import timedelta
from decimal import Decimal
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

    def test_dsr_sheet_view_permissions(self):
        self.client.login(username="member", password="password")
        url = reverse("dsr:dsr_sheet")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily Status Report")

    def test_dsr_inline_update(self):
        self.ticket.transition_to("resolved", actor=self.member)
        entry = DSREntry.objects.get(ticket=self.ticket)

        self.client.login(username="member", password="password")
        url = reverse("dsr:dsr_update", kwargs={"pk": entry.pk})
        response = self.client.post(url, {"hours_spent": "3.50", "notes": "Fixed certificate issue"})
        self.assertEqual(response.status_code, 302)

        entry.refresh_from_db()
        self.assertEqual(entry.hours_spent, Decimal("3.50"))
        self.assertEqual(entry.notes, "Fixed certificate issue")

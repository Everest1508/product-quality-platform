from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.products.models import Product
from apps.tickets import service
from apps.tickets.models import Ticket

User = get_user_model()


class TicketServiceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("owner", "o@t.local", "pass1234")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.product = Product.objects.create(company=self.company, name="App", slug="app")
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Bug", created_by=self.dev)

    def test_change_status_moves_logs_and_notifies(self):
        with mock.patch("apps.tickets.service.notify_ticket_status_changed") as hook:
            self.assertIsNone(service.change_status(self.ticket, "in_progress", self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "in_progress")
        hook.assert_called_once()
        row = ActivityLog.objects.get(event_type="ticket_status_changed")
        self.assertEqual(row.metadata["to"], "in_progress")

    def test_change_status_rejects_an_unknown_status_and_changes_nothing(self):
        msg = service.change_status(self.ticket, "bogus", self.owner, self.company)
        self.assertIn("not a valid status", msg)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")
        self.assertFalse(ActivityLog.objects.filter(event_type="ticket_status_changed").exists())

    def test_delete_rights(self):
        other = User.objects.create_user("x", "x@t.local", "pass1234")
        self.assertTrue(service.can_delete_ticket(self.owner, "owner", self.ticket))
        self.assertTrue(service.can_delete_ticket(self.dev, "developer", self.ticket))  # creator
        self.assertFalse(service.can_delete_ticket(other, "developer", self.ticket))

    def test_delete_ticket_removes_it_and_logs(self):
        key = service.delete_ticket(self.ticket, self.owner, self.company)
        self.assertEqual(key, f"{self.product.key}-001")
        self.assertFalse(Ticket.objects.filter(pk=self.ticket.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_deleted").exists())

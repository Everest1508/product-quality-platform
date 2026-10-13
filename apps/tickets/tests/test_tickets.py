import re
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket, TicketComment

User = get_user_model()


class TicketModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")

    def test_valid_transition(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        self.assertTrue(ticket.can_transition_to("assigned"))
        ticket.transition_to("assigned")
        self.assertEqual(ticket.status, "assigned")

    def test_invalid_transition(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        self.assertFalse(ticket.can_transition_to("bogus"))
        with self.assertRaises(ValueError):
            ticket.transition_to("bogus")

    def test_full_lifecycle(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        for status in ["assigned", "in_progress", "testing", "resolved", "closed"]:
            ticket.transition_to(status)
        self.assertEqual(ticket.status, "closed")


class TicketViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_ticket_list(self):
        response = self.client.get(reverse("tickets:ticket_list"))
        self.assertEqual(response.status_code, 200)


    def test_ticket_detail(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user, product=self.product,
        )
        response = self.client.get(reverse("tickets:ticket_detail", kwargs={"pk": ticket.pk}))
        self.assertEqual(response.status_code, 200)

    def test_ticket_detail_other_tenant(self):
        other = Company.objects.create(name="Other", slug="other")
        other_ticket = Ticket.objects.create(company=other, title="Other")
        response = self.client.get(reverse("tickets:ticket_detail", kwargs={"pk": other_ticket.pk}))
        self.assertEqual(response.status_code, 404)

    def test_status_change(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_status", kwargs={"pk": ticket.pk}),
            {"status": "assigned"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "assigned")

    def test_invalid_status_change(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_status", kwargs={"pk": ticket.pk}),
            {"status": "bogus"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "open")

    def test_assign_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"assignees": [self.user.pk]},
        )
        ticket.refresh_from_db()
        self.assertEqual(list(ticket.assignees.all()), [self.user])
        self.assertEqual(ticket.assigned_to, self.user)
        self.assertEqual(ticket.status, "assigned")

    def test_unassign_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
            assigned_to=self.user, status="assigned",
        )
        ticket.assignees.set([self.user])
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"assignees": []},
        )
        ticket.refresh_from_db()
        self.assertEqual(list(ticket.assignees.all()), [])
        self.assertIsNone(ticket.assigned_to)
        self.assertEqual(ticket.status, "open")

    def test_multi_assign_ticket(self):
        other = User.objects.create_user("bob", "bob@test.com", "pass1234")
        Membership.objects.create(user=other, company=self.company, role="developer")
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"assignees": [self.user.pk, other.pk]},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.assignees.count(), 2)
        self.assertEqual(ticket.assigned_to, self.user)

    def test_overdue_property(self):
        from django.utils import timezone
        from datetime import timedelta
        ticket = Ticket.objects.create(
            company=self.company, title="Late", created_by=self.user,
            deadline=timezone.now() - timedelta(hours=1), status="in_progress",
        )
        self.assertTrue(ticket.is_overdue)
        ticket.status = "resolved"
        ticket.save(update_fields=["status", "updated_at"])
        self.assertFalse(ticket.is_overdue)


    def test_kanban_is_default(self):
        response = self.client.get("/tickets/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "uiapi/shell.html")









class TicketProductAccessTest(TestCase):
    """A member restricted to certain products must not see or touch tickets
    belonging to products they have no access to (global tickets board)."""

    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")

        self.allowed = Product.objects.create(name="Allowed", slug="allowed", company=self.company)
        self.secret = Product.objects.create(name="Secret", slug="secret", company=self.company)
        ProductAccess.objects.create(user=self.dev, product=self.allowed, company=self.company)

        self.allowed_ticket = Ticket.objects.create(
            company=self.company, title="Allowed ticket", product=self.allowed,
        )
        self.secret_ticket = Ticket.objects.create(
            company=self.company, title="Secret ticket", product=self.secret,
        )
        self.orphan_ticket = Ticket.objects.create(
            company=self.company, title="No product ticket",
        )
        self.client.login(username="dev", password="pass1234")




    def test_cannot_open_inaccessible_ticket(self):
        response = self.client.get(
            reverse("tickets:ticket_detail", kwargs={"pk": self.secret_ticket.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_change_status_of_inaccessible_ticket(self):
        response = self.client.post(
            reverse("tickets:ticket_status", kwargs={"pk": self.secret_ticket.pk}),
            {"status": "closed"},
        )
        self.assertEqual(response.status_code, 404)
        self.secret_ticket.refresh_from_db()
        self.assertEqual(self.secret_ticket.status, "open")

    def test_can_change_status_of_accessible_ticket(self):
        response = self.client.post(
            reverse("tickets:ticket_status", kwargs={"pk": self.allowed_ticket.pk}),
            {"status": "closed"},
        )
        self.assertIn(response.status_code, (200, 302))
        self.allowed_ticket.refresh_from_db()
        self.assertEqual(self.allowed_ticket.status, "closed")








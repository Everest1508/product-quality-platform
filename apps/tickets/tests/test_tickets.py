from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.products.models import Product
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
            company=self.company, title="Test", created_by=self.user, status="closed",
        )
        self.assertFalse(ticket.can_transition_to("open"))
        with self.assertRaises(ValueError):
            ticket.transition_to("open")

    def test_full_lifecycle(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        for status in ["assigned", "in_progress", "testing", "resolved", "closed"]:
            ticket.transition_to(status)
        self.assertEqual(ticket.status, "closed")

    def test_cannot_transition_closed_to_anything(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", status="closed",
        )
        self.assertEqual(ticket.VALID_TRANSITIONS["closed"], [])


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

    def test_create_ticket(self):
        response = self.client.post(reverse("tickets:ticket_create"), {
            "title": "Login bug",
            "description": "Cannot login",
            "ticket_type": "bug",
            "priority": "high",
            "product": self.product.pk,
        })
        self.assertRedirects(response, reverse("tickets:ticket_detail", kwargs={"pk": 1}))
        self.assertEqual(Ticket.objects.count(), 1)
        ticket = Ticket.objects.first()
        self.assertEqual(ticket.created_by, self.user)
        self.assertEqual(ticket.company, self.company)

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
            company=self.company, title="Test", created_by=self.user, status="closed",
        )
        response = self.client.post(
            reverse("tickets:ticket_status", kwargs={"pk": ticket.pk}),
            {"status": "open"},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, "closed")

    def test_assign_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"assigned_to": self.user.pk},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.user)
        self.assertEqual(ticket.status, "assigned")

    def test_unassign_ticket(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
            assigned_to=self.user, status="assigned",
        )
        response = self.client.post(
            reverse("tickets:ticket_assign", kwargs={"pk": ticket.pk}),
            {"assigned_to": ""},
        )
        ticket.refresh_from_db()
        self.assertIsNone(ticket.assigned_to)
        self.assertEqual(ticket.status, "open")

    def test_add_comment(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_comment", kwargs={"pk": ticket.pk}),
            {"body": "This is a comment"},
        )
        self.assertEqual(TicketComment.objects.count(), 1)
        comment = TicketComment.objects.first()
        self.assertEqual(comment.body, "This is a comment")
        self.assertEqual(comment.author, self.user)

    def test_htmx_comment(self):
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        response = self.client.post(
            reverse("tickets:ticket_comment", kwargs={"pk": ticket.pk}),
            {"body": "HTMX comment"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("HTMX comment", response.content.decode())

    def test_filter_by_status(self):
        Ticket.objects.create(company=self.company, title="Open", status="open")
        Ticket.objects.create(company=self.company, title="Closed", status="closed")
        response = self.client.get(reverse("tickets:ticket_list") + "?status=open")
        self.assertEqual(len(response.context["page"].object_list), 1)

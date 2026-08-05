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

    def test_create_ticket_with_assignees_and_deadline(self):
        from django.utils import timezone
        from datetime import timedelta
        bob = User.objects.create_user("bob", "bob@test.com", "pass1234")
        Membership.objects.create(user=bob, company=self.company, role="developer")
        deadline = timezone.now() + timedelta(days=2)
        response = self.client.post(reverse("tickets:ticket_create"), {
            "title": "With deadline",
            "ticket_type": "bug",
            "priority": "high",
            "product": self.product.pk,
            "assignees": [self.user.pk, bob.pk],
            "deadline": deadline.isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        ticket = Ticket.objects.get(title="With deadline")
        self.assertEqual(ticket.assignees.count(), 2)
        self.assertEqual(ticket.deadline, deadline)

    def test_kanban_is_default(self):
        response = self.client.get("/tickets/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/ticket_kanban.html")

    def test_kanban_filters_overdue(self):
        from django.utils import timezone
        from datetime import timedelta
        Ticket.objects.create(
            company=self.company, title="Late", created_by=self.user,
            deadline=timezone.now() - timedelta(hours=1), status="in_progress",
        )
        Ticket.objects.create(
            company=self.company, title="On time", created_by=self.user, status="open",
        )
        response = self.client.get(reverse("tickets:ticket_board") + "?overdue=1")
        total = 0
        for col in response.context["columns"]:
            total += len(col["tickets"])
        self.assertEqual(total, 1)

    def test_filter_by_status(self):
        Ticket.objects.create(company=self.company, title="Open", status="open")
        Ticket.objects.create(company=self.company, title="Closed", status="closed")
        response = self.client.get(reverse("tickets:ticket_list") + "?status=open")
        self.assertEqual(len(response.context["page"].object_list), 1)


class TicketDeleteTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.member = User.objects.create_user("member", "member@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.member, company=self.company, role="developer")
        self.ticket = Ticket.objects.create(company=self.company, title="Doomed", created_by=self.owner)

    def test_admin_can_delete_ticket(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": self.ticket.pk}))
        self.assertRedirects(response, reverse("tickets:ticket_board"))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_non_admin_cannot_delete_ticket(self):
        self.client.login(username="member", password="pass1234")
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": self.ticket.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_delete_other_tenant_ticket(self):
        other = Company.objects.create(name="Other", slug="other")
        other_ticket = Ticket.objects.create(company=other, title="Not yours")
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": other_ticket.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 2)

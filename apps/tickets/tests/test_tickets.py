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
        ProductAccess.objects.create(user=bob, product=self.product, company=self.company)
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
        self.assertTemplateUsed(response, "uiapi/shell.html")



    def test_set_deadline(self):
        from django.utils import timezone
        from datetime import timedelta
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        deadline = timezone.now() + timedelta(days=2)
        response = self.client.post(
            reverse("tickets:ticket_deadline", kwargs={"pk": ticket.pk}),
            {"deadline": deadline.isoformat()},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.deadline, deadline)

    def test_clear_deadline(self):
        from django.utils import timezone
        from datetime import timedelta
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
            deadline=timezone.now() + timedelta(days=2),
        )
        response = self.client.post(
            reverse("tickets:ticket_deadline", kwargs={"pk": ticket.pk}),
            {"deadline": ""},
        )
        ticket.refresh_from_db()
        self.assertIsNone(ticket.deadline)

    def test_deadline_htmx(self):
        from django.utils import timezone
        from datetime import timedelta
        ticket = Ticket.objects.create(
            company=self.company, title="Test", created_by=self.user,
        )
        deadline = timezone.now() + timedelta(days=1)
        response = self.client.post(
            reverse("tickets:ticket_deadline", kwargs={"pk": ticket.pk}),
            {"deadline": deadline.isoformat()},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/partials/_ticket_deadline.html")
        ticket.refresh_from_db()
        self.assertEqual(ticket.deadline, deadline)


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

    def test_creator_can_delete_own_ticket(self):
        self.client.login(username="member", password="pass1234")
        ticket = Ticket.objects.create(company=self.company, title="My ticket", created_by=self.member)
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": ticket.pk}))
        self.assertRedirects(response, reverse("tickets:ticket_board"))
        self.assertEqual(Ticket.objects.count(), 1)

    def test_non_creator_cannot_delete_others_ticket(self):
        self.client.login(username="member", password="pass1234")
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": self.ticket.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_following_and_unfollowing_are_audited(self):
        from apps.dashboards.models import ActivityLog

        ticket = Ticket.objects.create(
            company=self.company, title="Follow me", created_by=self.owner,
        )
        self.client.login(username="member", password="pass1234")
        self.client.post(reverse("tickets:ticket_follow", args=[ticket.pk]))
        followed = ActivityLog.objects.get(event_type="ticket_followed", company=self.company)
        self.assertEqual(followed.target_object_id, ticket.pk)
        self.client.post(reverse("tickets:ticket_follow", args=[ticket.pk]))
        self.assertTrue(
            ActivityLog.objects.filter(event_type="ticket_unfollowed", company=self.company).exists()
        )

    def test_delete_other_tenant_ticket(self):
        other = Company.objects.create(name="Other", slug="other")
        other_ticket = Ticket.objects.create(company=other, title="Not yours")
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(reverse("tickets:ticket_delete", kwargs={"pk": other_ticket.pk}))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 2)


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

    def test_create_skips_assignee_without_product_access(self):
        self.client.login(username="owner", password="pass1234")
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()
        response = self.client.post(reverse("tickets:ticket_create"), {
            "title": "T", "ticket_type": "bug", "priority": "medium",
            "product": self.secret.pk, "assignees": [self.dev.pk, self.owner.pk],
        })
        ticket = Ticket.objects.get(title="T")
        self.assertEqual(response.status_code, 302)
        # dev has no access to the Secret product, so is skipped rather than failing the form
        self.assertEqual(set(ticket.assignees.values_list("pk", flat=True)), {self.owner.pk})



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



class AssigneeDropdownLabellingTest(TicketViewTest):
    """The assignees picker hides the native select and stands up a div.

    `.assignee-dd__native` is `display:none`, so the `role="button"` trigger is
    the control assistive tech actually meets. As a bare interactive div it had
    no accessible name, no `aria-haspopup` and no expansion state, and its
    "remove" chip said the same thing for every assignee.
    """

    def trigger(self):
        body = self.client.get(reverse("tickets:ticket_create")).content.decode()
        start = body.index('class="assignee-dd__trigger"')
        start = body.rindex("<div", 0, start)
        return body[start : body.index(">", start) + 1]

    def test_trigger_is_named_and_advertises_what_it_opens(self):
        tag = self.trigger()
        self.assertIn('aria-label="Assignees"', tag)
        self.assertIn('aria-haspopup="listbox"', tag)
        self.assertIn("aria-expanded", tag)

    def test_the_search_box_inside_the_panel_is_named(self):
        body = self.client.get(reverse("tickets:ticket_create")).content.decode()
        panel = body[body.index('class="assignee-dd__panel"') :]
        search = re.search(r'<input[^>]*class="assignee-dd__search"[^>]*>', panel)
        self.assertIsNotNone(search)
        self.assertIn("aria-label=", search.group(0))

    def test_remove_chip_names_the_assignee_it_removes(self):
        body = self.client.get(reverse("tickets:ticket_create")).content.decode()
        self.assertNotIn('aria-label="Remove assignee"', body)
        self.assertIn("'Remove ' + opt.name", body)




class TicketFormErrorToastTest(TicketProductAccessTest):
    def test_invalid_create_shows_a_toast_naming_the_field(self):
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()
        response = self.client.post(reverse("tickets:ticket_create"), {"title": "", "ticket_type": "bug", "priority": "nope"})
        msgs = [str(m) for m in response.context["messages"]]
        self.assertTrue(any("Title" in m and "Priority" in m for m in msgs), msgs)

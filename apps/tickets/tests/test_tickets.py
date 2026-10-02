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

    def test_board_hides_inaccessible_product_tickets(self):
        response = self.client.get(reverse("tickets:ticket_board"))
        shown = {t.pk for col in response.context["columns"] for t in col["tickets"]}
        self.assertIn(self.allowed_ticket.pk, shown)
        self.assertIn(self.orphan_ticket.pk, shown)
        self.assertNotIn(self.secret_ticket.pk, shown)

    def test_list_hides_inaccessible_product_tickets(self):
        response = self.client.get(reverse("tickets:ticket_list"))
        shown = {t.pk for t in response.context["page"].object_list}
        self.assertNotIn(self.secret_ticket.pk, shown)

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

    def test_bulk_delete_skips_inaccessible_tickets(self):
        # dev created both tickets but only has access to `allowed`
        Ticket.objects.filter(pk__in=[self.secret_ticket.pk, self.allowed_ticket.pk]).update(
            created_by=self.dev
        )
        self.client.post(
            reverse("tickets:ticket_bulk_delete"),
            {"ticket_ids[]": [self.secret_ticket.pk, self.allowed_ticket.pk]},
        )
        self.assertTrue(Ticket.objects.filter(pk=self.secret_ticket.pk).exists())
        self.assertFalse(Ticket.objects.filter(pk=self.allowed_ticket.pk).exists())


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


class TicketFilterDropdownTest(TestCase):
    """The filter bar's choice controls are `<details>` + radios, not `<select>`.

    The point of that swap is that the values keep posting with no JavaScript
    and still fire a native `change` for the htmx form, so these pin the
    rendered contract rather than the styling.
    """

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def _bar(self, query=""):
        html = self.client.get(reverse("tickets:ticket_list") + query).content.decode()
        start = html.index("<form class=\"toolbar\"")
        # The end has to be searched from `start`: an earlier </form> belongs to
        # the topbar, and slicing to it yields an empty string.
        return html[start:html.index("</form>", start)]

    def test_the_filter_bar_has_no_native_select_left(self):
        self.assertNotIn("<select", self._bar())

    def test_every_filter_still_posts_a_key_even_when_left_alone(self):
        """An unchecked radio group submits nothing, so a filter the user never
        touches would vanish from the query string instead of arriving as "".
        """
        bar = self._bar()
        for name in ("status", "type", "priority", "assigned"):
            self.assertRegex(bar, rf'name="{name}" value="[^"]*"[^>]*checked', msg=name)
        self.assertRegex(bar, r'name="sort" value="[^"]*"[^>]*checked')

    def test_the_current_filter_is_prechecked_so_the_page_round_trips(self):
        bar = self._bar("?type=feature&priority=low")
        self.assertIn('name="type" value="feature" data-label="Feature" checked', bar)
        self.assertIn('name="priority" value="low" data-label="Low" checked', bar)

    def test_the_assignee_filter_offers_the_two_sentinels_and_every_member(self):
        """`assigned` means three different things, not one.

        `TicketListView` resolves it as "me" -> me, "unassigned" -> no
        assignees, anything else -> `assignees__id=<pk>`, so the dropdown has to
        offer all three. Replacing the `<select>` with a hand-written list of
        sentinels silently dropped the member branch, which is the one an admin
        actually filters by.
        """
        mate = User.objects.create_user("bob", "bob@test.com", "pass1234")
        Membership.objects.create(
            user=mate, company=self.company, role="developer"
        )
        bar = self._bar()
        for value in ("me", "unassigned", str(mate.pk)):
            with self.subTest(value=value):
                self.assertIn(f'name="assigned" value="{value}"', bar)
        # No first/last name is set, so `obj_pairs` falls back to the username.
        # This is the assertion that would catch a bound-method repr leaking.
        self.assertIn(">bob</span>", bar)
        self.assertNotIn("bound method", bar)

    def test_a_member_filter_is_still_accepted_by_the_view(self):
        """End-to-end half of the above: the member option is not decorative."""
        mate = User.objects.create_user("bob", "bob@test.com", "pass1234")
        Membership.objects.create(
            user=mate, company=self.company, role="developer"
        )
        Ticket.objects.create(
            company=self.company, product=self.product, title="Mine",
            created_by=self.user,
        )
        # `assigned_to` is a separate FK kept in sync by `set_assignees`, and the
        # view filters on the M2M -- so the write has to go through the real path.
        theirs = Ticket.objects.create(
            company=self.company, product=self.product, title="Theirs",
            created_by=self.user,
        )
        theirs.set_assignees([mate])
        # The rows render outside the toolbar form, in #ticket-results.
        page = self.client.get(
            reverse("tickets:ticket_list") + f"?assigned={mate.pk}"
        ).content.decode()
        self.assertIn("Theirs", page)
        self.assertNotIn("Mine", page)
        self.assertEqual(theirs.assigned_to_id, mate.pk)

        bar = self._bar(f"?assigned={mate.pk}")
        # The choice has to survive the round trip, and the closed trigger has
        # to name the person rather than fall back to the placeholder.
        self.assertIn(
            f'name="assigned" value="{mate.pk}" data-label="bob" checked', bar
        )
        self.assertIn(">bob</span>", bar)


    def test_an_all_filter_is_a_real_option_rather_than_a_missing_key(self):
        bar = self._bar("?type=")
        self.assertIn('name="type" value="" data-label="All types" checked', bar)

    def test_the_trigger_shows_the_current_value_without_javascript(self):
        bar = self._bar("?type=question")
        self.assertIn("data-dd-label>Question<", bar)

    def test_filtering_still_narrows_the_list(self):
        Ticket.objects.create(company=self.company, title="A bug", created_by=self.user,
                              status="open", ticket_type="bug")
        Ticket.objects.create(company=self.company, title="A feature", created_by=self.user,
                              status="open", ticket_type="feature")
        html = self.client.get(reverse("tickets:ticket_list") + "?type=feature").content.decode()
        self.assertIn("A feature", html)
        self.assertNotIn("A bug", html)

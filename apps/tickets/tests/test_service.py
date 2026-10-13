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


from datetime import datetime  # noqa: E402

from django.utils import timezone  # noqa: E402

from apps.notifications.models import Notification  # noqa: E402
from apps.products.models import ProductAccess  # noqa: E402


class TicketActionServiceTest(TicketServiceTest):
    def test_set_priority_logs_and_rejects_unknown(self):
        self.assertIsNone(service.set_priority(self.ticket, "critical", self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, "critical")
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_priority_changed").exists())
        self.assertIn("not a valid priority", service.set_priority(self.ticket, "huge", self.owner, self.company))

    def test_assign_moves_open_to_assigned_and_back(self):
        msg = service.assign(self.ticket, [self.dev.pk], self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertEqual((self.ticket.status, list(self.ticket.assignees.all())), ("assigned", [self.dev]))
        self.assertIn("assigned to", msg)
        self.assertIn("Status is now Assigned", msg)
        self.assertIn("unassigned", service.assign(self.ticket, [], self.owner, self.company))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, "open")

    def test_assign_ignores_people_outside_the_company(self):
        stranger = User.objects.create_user("zed", "z@t.local", "pass1234")
        service.assign(self.ticket, [stranger.pk, self.dev.pk], self.owner, self.company)
        self.assertEqual(list(self.ticket.assignees.all()), [self.dev])

    def test_set_deadline_sets_and_clears_and_logs(self):
        when = timezone.make_aware(datetime(2026, 10, 20, 10, 0), timezone.get_current_timezone())
        service.set_deadline(self.ticket, when, self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.deadline, when)
        service.set_deadline(self.ticket, None, self.owner, self.company)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.deadline)
        self.assertEqual(ActivityLog.objects.filter(event_type="ticket_deadline_changed").count(), 2)

    def test_toggle_follow(self):
        self.assertTrue(service.toggle_follow(self.ticket, self.owner, self.company))
        self.assertFalse(service.toggle_follow(self.ticket, self.owner, self.company))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_followed").exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_unfollowed").exists())

    def test_comment_stores_mentions_and_notifies_without_duplicates(self):
        ProductAccess.objects.create(company=self.company, user=self.dev, product=self.product)
        outsider = User.objects.create_user("out", "x@t.local", "pass1234")
        Membership.objects.create(user=outsider, company=self.company, role="developer")  # no product access
        self.ticket.set_assignees([self.dev])
        c = service.add_comment(self.ticket, "hi @dev and @out", self.owner, self.company)
        self.assertEqual([u.username for u in c.mentions.all()], ["dev"])  # outsider cannot open it
        kinds = {(n.user.username, n.kind) for n in Notification.objects.all()}
        self.assertIn(("dev", "mention"), kinds)
        self.assertNotIn(("dev", "comment"), kinds)  # nobody gets both
        self.assertFalse(Notification.objects.filter(user=outsider).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_commented").exists())

    def test_create_ticket_skips_assignees_without_product_access_and_warns(self):
        ProductAccess.objects.create(company=self.company, user=self.dev, product=self.product)
        nobody = User.objects.create_user("nb", "n@t.local", "pass1234")
        Membership.objects.create(user=nobody, company=self.company, role="developer")
        ticket, form, warnings = service.create_ticket(
            {"title": "New", "ticket_type": "bug", "priority": "high", "product": self.product.pk,
             "assignees": [self.dev.pk, nobody.pk]},
            self.owner, self.company,
        )
        self.assertEqual(list(ticket.assignees.all()), [self.dev])
        self.assertEqual(ticket.created_by, self.owner)
        self.assertEqual(ticket.source, "manual")
        self.assertIn("Not assigned (no access to App)", warnings[0])
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created").exists())

    def test_create_ticket_invalid_returns_the_form(self):
        ticket, form, warnings = service.create_ticket({"title": ""}, self.owner, self.company)
        self.assertIsNone(ticket)
        self.assertIn("title", form.errors)

    def test_update_ticket(self):
        ticket, form = service.update_ticket(
            {"title": "Renamed", "ticket_type": "bug", "priority": "low", "status": "testing", "assignees": [self.dev.pk]},
            self.ticket, self.owner, self.company,
        )
        ticket.refresh_from_db()
        self.assertEqual((ticket.title, ticket.status), ("Renamed", "testing"))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_updated").exists())

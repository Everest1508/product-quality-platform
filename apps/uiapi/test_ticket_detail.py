from datetime import datetime

from django.test import Client
from django.utils import timezone

from apps.dashboards.models import ActivityLog
from apps.tickets.models import Ticket
from apps.uiapi.test_tickets import Base, member


class TicketDetailApiTest(Base):
    def url(self, t):
        return f"/ui-api/v1/tickets/{t.pk}/"

    def test_detail_shape(self):
        t = self.make(self.p_open, "Login bug", description="Cannot sign in", created_by=self.owner)
        t.set_assignees([self.dev])
        t.watchers.add(self.dev)
        self.login("dev")
        data = self.client.get(self.url(t)).json()
        self.assertEqual(data["ticket"]["key"], t.key)
        self.assertEqual(data["ticket"]["description"], "Cannot sign in")
        self.assertEqual(data["ticket"]["created_by"]["name"], "owner")
        self.assertTrue(data["following"])
        self.assertEqual(data["watcher_count"], 1)
        self.assertEqual(data["statuses"][0], ["open", "Open"])
        self.assertIn("dev", [m["username"] for m in data["members"]])
        self.assertIn("dev", [c["username"] for c in data["mention_candidates"]])

    def test_deadline_is_the_company_wall_clock(self):
        when = timezone.make_aware(datetime(2026, 10, 20, 10, 5), timezone.get_current_timezone())
        t = self.make(self.p_open, deadline=when)
        self.login("owner")
        self.assertEqual(self.client.get(self.url(t)).json()["ticket"]["deadline_local"], "2026-10-20T10:05")

    def test_comments_come_with_their_mentions(self):
        from apps.tickets.service import add_comment

        t = self.make(self.p_open)
        add_comment(t, "hi @dev", self.owner, self.acme)
        self.login("owner")
        c = self.client.get(self.url(t)).json()["comments"][0]
        self.assertEqual((c["body"], c["mentions"], c["author"]["name"]), ("hi @dev", ["dev"], "owner"))

    def test_linked_error_url_follows_the_product(self):
        from apps.ingestion.models import ErrorGroup

        eg = ErrorGroup.objects.create(company=self.acme, product=self.p_open, fingerprint="f", title="Boom")
        t = self.make(self.p_open, linked_error_group=eg)
        self.login("owner")
        link = self.client.get(self.url(t)).json()["ticket"]["linked_error"]
        self.assertEqual(link, {"id": eg.pk, "title": "Boom", "url": f"/products/{self.p_open.pk}/errors/{eg.pk}/"})

    def test_inaccessible_and_foreign_tickets_are_404(self):
        hidden, foreign = self.make(self.p_hidden), self.make(self.p_foreign)
        self.login("dev")
        self.assertEqual(self.client.get(self.url(hidden)).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(self.url(foreign)).status_code, 404)

    def test_a_ticket_without_a_product_lists_all_company_members(self):
        t = Ticket.objects.create(company=self.acme, title="Company-wide")
        self.login("dev")
        names = [m["username"] for m in self.client.get(self.url(t)).json()["members"]]
        self.assertEqual(sorted(names), ["dev", "owner"])

    def test_anonymous_is_403(self):
        t = self.make(self.p_open)
        self.assertEqual(Client().get(self.url(t)).status_code, 403)


class TicketEditApiTest(Base):
    def patch(self, t, body):
        return self.client.patch(f"/ui-api/v1/tickets/{t.pk}/", body, content_type="application/json")

    def good(self, **over):
        return {"title": "Renamed", "description": "d", "ticket_type": "bug", "priority": "low", "status": "testing",
                "assignees": [], "deadline": "", **over}

    def test_edit_saves_and_logs(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.patch(t, self.good(assignees=[self.dev.pk], deadline="2026-10-20T10:00"))
        self.assertEqual(r.status_code, 200)
        t.refresh_from_db()
        self.assertEqual((t.title, t.status, list(t.assignees.all())), ("Renamed", "testing", [self.dev]))
        self.assertEqual(r.json()["ticket"]["deadline_local"], "2026-10-20T10:00")
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_updated").exists())

    def test_clearing_the_deadline(self):
        t = self.make(self.p_open, deadline=timezone.now())
        self.login("owner")
        self.assertEqual(self.patch(t, self.good(deadline="")).status_code, 200)
        t.refresh_from_db()
        self.assertIsNone(t.deadline)

    def test_validation_errors_are_per_field_and_save_nothing(self):
        t = self.make(self.p_open, "Keep me")
        self.login("owner")
        r = self.patch(t, self.good(title="", deadline="not a date"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["errors"])
        self.assertIn("deadline", r.json()["errors"])
        self.assertTrue(r.json()["detail"].startswith("Could not save."))
        t.refresh_from_db()
        self.assertEqual(t.title, "Keep me")

    def test_edit_needs_access_and_csrf(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        self.assertEqual(self.patch(hidden, self.good()).status_code, 404)
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        t = self.make(self.p_open)
        r = strict.patch(f"/ui-api/v1/tickets/{t.pk}/", self.good(), content_type="application/json")
        self.assertEqual(r.status_code, 403)

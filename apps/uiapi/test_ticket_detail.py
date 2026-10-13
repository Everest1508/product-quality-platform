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


class TicketActionsApiTest(Base):
    def post(self, t, action, body=None):
        return self.client.post(f"/ui-api/v1/tickets/{t.pk}/{action}/", body or {}, content_type="application/json")

    def test_priority(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "priority", {"priority": "critical"})
        self.assertEqual(r.json()["ticket"]["priority"], "critical")
        self.assertEqual(self.post(t, "priority", {"priority": "huge"}).status_code, 400)

    def test_assign_sets_status_and_ignores_strangers(self):
        t = self.make(self.p_open)
        stranger = member("zed", self.other)
        self.login("owner")
        data = self.post(t, "assign", {"assignees": [self.dev.pk, stranger.pk]}).json()
        self.assertEqual([a["id"] for a in data["ticket"]["assignees"]], [self.dev.pk])
        self.assertEqual(data["ticket"]["status"], "assigned")
        self.assertIn("assigned to", data["message"])
        self.assertEqual(self.post(t, "assign", {"assignees": []}).json()["ticket"]["status"], "open")

    def test_assign_survives_garbage_ids(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "assign", {"assignees": ["x", None, self.dev.pk]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([a["id"] for a in r.json()["ticket"]["assignees"]], [self.dev.pk])

    def test_deadline_set_clear_and_garbage(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "deadline", {"deadline": "2026-10-20T10:00"})
        self.assertEqual(r.json()["ticket"]["deadline_local"], "2026-10-20T10:00")
        self.assertEqual(self.post(t, "deadline", {"deadline": None}).json()["ticket"]["deadline_local"], "")
        self.assertEqual(self.post(t, "deadline", {"deadline": "soon"}).status_code, 400)

    def test_follow_toggles(self):
        t = self.make(self.p_open)
        self.login("dev")
        r = self.post(t, "follow")
        self.assertEqual((r.json()["following"], r.json()["watcher_count"]), (True, 1))
        self.assertIn("following", r.json()["message"])
        self.assertFalse(self.post(t, "follow").json()["following"])

    def test_comment_with_mentions(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "comments", {"body": "hello @dev"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["comments"][0]["mentions"], ["dev"])

    def test_empty_comment_is_400(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post(t, "comments", {"body": "   "})
        self.assertEqual((r.status_code, r.json()["detail"]), (400, "Comment cannot be empty."))
        self.assertEqual(t.comments.count(), 0)

    def test_every_action_needs_access(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        for action, body in [("priority", {"priority": "low"}), ("assign", {"assignees": []}), ("deadline", {"deadline": None}),
                             ("follow", {}), ("comments", {"body": "x"})]:
            self.assertEqual(self.post(hidden, action, body).status_code, 404, action)
        self.assertEqual(hidden.comments.count(), 0)


class TicketCreateApiTest(Base):
    url = "/ui-api/v1/tickets/"

    def post(self, body):
        return self.client.post(self.url, body, content_type="application/json")

    def good(self, **over):
        return {"title": "New bug", "description": "", "ticket_type": "bug", "priority": "high",
                "product": self.p_open.pk, "assignees": [], "deadline": "", **over}

    def test_create_returns_key_url_and_logs(self):
        self.login("dev")
        r = self.post(self.good())
        self.assertEqual(r.status_code, 201)
        t = Ticket.objects.get(title="New bug")
        self.assertEqual((r.json()["key"], r.json()["url"]), (t.key, f"/products/{self.p_open.pk}/tickets/{t.pk}/"))
        self.assertEqual((t.created_by, t.source, t.company), (self.dev, "manual", self.acme))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created").exists())

    def test_cannot_create_in_a_product_the_user_cannot_open(self):
        self.login("dev")
        r = self.post(self.good(product=self.p_hidden.pk))
        self.assertEqual(r.status_code, 400)
        self.assertIn("product", r.json()["errors"])
        self.assertFalse(Ticket.objects.filter(title="New bug").exists())

    def test_cannot_create_in_another_companys_product(self):
        self.login("owner")
        self.assertEqual(self.post(self.good(product=self.p_foreign.pk)).status_code, 400)
        self.assertFalse(Ticket.objects.filter(title="New bug").exists())

    def test_assignees_without_product_access_are_skipped_with_a_warning(self):
        outsider = member("out", self.acme)  # company member, no access to p_open
        self.login("owner")
        r = self.post(self.good(assignees=[self.dev.pk, outsider.pk]))
        self.assertEqual([a["id"] for a in r.json()["ticket"]["assignees"]], [self.dev.pk])
        self.assertIn("Not assigned (no access to Open)", r.json()["warnings"][0])

    def test_company_wide_ticket_without_a_product(self):
        self.login("owner")
        r = self.post(self.good(product=None))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["url"], f"/tickets/{Ticket.objects.get(title='New bug').pk}/")

    def test_validation_errors(self):
        self.login("owner")
        r = self.post(self.good(title="", deadline="nope"))
        self.assertEqual(r.status_code, 400)
        self.assertTrue({"title", "deadline"} <= set(r.json()["errors"]))
        self.assertEqual(Ticket.objects.count(), 0)

    def test_csrf_and_anonymous(self):
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        self.assertEqual(strict.post(self.url, self.good(), content_type="application/json").status_code, 403)
        self.assertEqual(Client().post(self.url, self.good(), content_type="application/json").status_code, 403)


class TicketDeleteApiTest(Base):
    def test_delete_another_companys_ticket_is_404(self):
        t = self.make(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{t.pk}/").status_code, 404)
        self.assertTrue(Ticket.objects.filter(pk=t.pk).exists())

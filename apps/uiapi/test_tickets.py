from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


def member(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.acme = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = member("owner", self.acme, "owner")
        self.dev = member("dev", self.acme)
        self.p_open = Product.objects.create(company=self.acme, name="Open", slug="open")
        self.p_hidden = Product.objects.create(company=self.acme, name="Hidden", slug="hidden")
        self.p_foreign = Product.objects.create(company=self.other, name="Foreign", slug="foreign")
        ProductAccess.objects.create(company=self.acme, user=self.dev, product=self.p_open)

    def make(self, product, title="t", **kw):
        return Ticket.objects.create(company=product.company, product=product, title=title, **kw)

    def login(self, name):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.acme.pk
        s.save()


class TicketListApiTest(Base):
    url = "/ui-api/v1/tickets/"

    def test_list_shape_and_key(self):
        t = self.make(self.p_open, "Login bug", priority="high")
        t.set_assignees([self.dev])
        self.login("dev")
        data = self.client.get(self.url).json()
        self.assertEqual(data["view"], "list")
        item = data["items"][0]
        self.assertEqual(item["key"], t.key)
        self.assertEqual(item["priority_label"], "High")
        self.assertEqual(item["product"], {"id": self.p_open.pk, "name": "Open"})
        self.assertEqual(item["assignees"][0]["initial"], "D")
        self.assertEqual(item["url"], f"/products/{self.p_open.pk}/tickets/{t.pk}/")
        self.assertTrue(item["can_delete"] is False)  # dev is not the creator
        self.assertEqual(data["page"]["count"], 1)

    def test_a_developer_only_sees_products_they_can_open(self):
        self.make(self.p_open, "mine")
        self.make(self.p_hidden, "secret")
        self.make(self.p_foreign, "foreign")
        self.login("dev")
        self.assertEqual([i["title"] for i in self.client.get(self.url).json()["items"]], ["mine"])
        self.login("owner")
        self.assertEqual(self.client.get(self.url).json()["page"]["count"], 2)  # never the other company's

    def test_product_scope_requires_access(self):
        self.make(self.p_hidden, "secret")
        self.login("dev")
        r = self.client.get(self.url, {"product": self.p_hidden.pk, "scope": "product"})
        self.assertEqual(r.status_code, 404)

    def test_product_scope_limits_to_that_product(self):
        self.make(self.p_open, "in")
        self.make(self.p_hidden, "out")
        self.login("owner")
        r = self.client.get(self.url, {"product": self.p_open.pk, "scope": "product"}).json()
        self.assertEqual([i["title"] for i in r["items"]], ["in"])

    def test_product_filter_cannot_reach_another_companys_product(self):
        self.make(self.p_foreign, "foreign")
        self.login("owner")
        self.assertEqual(self.client.get(self.url, {"product": self.p_foreign.pk}).json()["page"]["count"], 0)
        r = self.client.get(self.url, {"product": self.p_foreign.pk, "scope": "product"})
        self.assertEqual(r.status_code, 404)

    def test_filters_and_open_count(self):
        self.make(self.p_open, "alpha bug", ticket_type="bug", priority="high", status="open")
        self.make(self.p_open, "beta feature", ticket_type="feature", priority="low", status="resolved")
        self.login("owner")
        r = self.client.get(self.url, {"q": "alpha"}).json()
        self.assertEqual([i["title"] for i in r["items"]], ["alpha bug"])
        r = self.client.get(self.url, {"type": "feature"}).json()
        self.assertEqual([i["title"] for i in r["items"]], ["beta feature"])
        r = self.client.get(self.url, {"status": "resolved"}).json()
        self.assertEqual(r["page"]["count"], 1)
        r = self.client.get(self.url).json()
        self.assertEqual((r["page"]["count"], r["open_count"]), (2, 1))

    def test_assignee_filters_do_not_duplicate(self):
        t = self.make(self.p_open, "two people")
        t.set_assignees([self.dev, self.owner])
        self.make(self.p_open, "nobody")
        self.login("owner")
        self.assertEqual(self.client.get(self.url, {"assigned": self.dev.pk}).json()["page"]["count"], 1)
        titles = [i["title"] for i in self.client.get(self.url, {"assigned": "unassigned"}).json()["items"]]
        self.assertEqual(titles, ["nobody"])
        self.assertEqual(self.client.get(self.url, {"assigned": "me"}).json()["page"]["count"], 1)

    def test_overdue_excludes_resolved(self):
        past = timezone.now() - timedelta(days=1)
        self.make(self.p_open, "late", deadline=past)
        self.make(self.p_open, "late but done", deadline=past, status="resolved")
        self.login("owner")
        titles = [i["title"] for i in self.client.get(self.url, {"overdue": "1"}).json()["items"]]
        self.assertEqual(titles, ["late"])

    def test_pagination_clamps_and_survives_garbage(self):
        for i in range(30):
            self.make(self.p_open, f"t{i}")
        self.login("owner")
        r = self.client.get(self.url, {"page": 99}).json()
        self.assertEqual((r["page"]["number"], r["page"]["num_pages"], len(r["items"])), (2, 2, 5))
        self.assertEqual(self.client.get(self.url, {"page": "abc"}).json()["page"]["number"], 1)

    def test_board_has_every_status_column(self):
        self.make(self.p_open, "a", status="open")
        self.make(self.p_open, "b", status="testing")
        self.login("owner")
        data = self.client.get(self.url, {"view": "board"}).json()
        self.assertEqual(
            [c["key"] for c in data["columns"]],
            ["open", "assigned", "in_progress", "testing", "resolved", "closed"],
        )
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["open_count"], 2)
        self.assertEqual(len(data["columns"][3]["tickets"]), 1)

    def test_hostile_title_is_returned_as_data(self):
        self.make(self.p_open, "<script>alert(1)</script>")
        self.login("owner")
        self.assertEqual(self.client.get(self.url).json()["items"][0]["title"], "<script>alert(1)</script>")

    def test_anonymous_is_403(self):
        self.assertEqual(Client().get(self.url).status_code, 403)


class TicketMetaApiTest(Base):
    url = "/ui-api/v1/tickets/meta/"

    def test_meta_lists_accessible_products_and_members(self):
        self.login("dev")
        data = self.client.get(self.url).json()
        self.assertEqual([p["name"] for p in data["products"]], ["Open"])
        self.assertIn("owner", [m["name"] for m in data["members"]])
        self.assertEqual(data["statuses"][0], ["open", "Open"])

    def test_meta_scoped_to_a_product_lists_that_products_users(self):
        self.login("owner")
        data = self.client.get(self.url, {"product": self.p_open.pk, "scope": "product"}).json()
        self.assertEqual(data["products"], [])
        self.assertIn("dev", [m["name"] for m in data["members"]])

    def test_meta_for_an_inaccessible_product_is_404(self):
        self.login("dev")
        r = self.client.get(self.url, {"product": self.p_hidden.pk, "scope": "product"})
        self.assertEqual(r.status_code, 404)


from unittest import mock  # noqa: E402

from apps.dashboards.models import ActivityLog  # noqa: E402


class TicketMutationApiTest(Base):
    def post_json(self, url, body):
        return self.client.post(url, body, content_type="application/json")

    def test_status_move_works_and_runs_the_side_effects(self):
        t = self.make(self.p_open)
        watcher = member("watcher", self.acme)
        ProductAccess.objects.create(company=self.acme, user=watcher, product=self.p_open)
        t.watchers.add(watcher)
        self.login("owner")
        with mock.patch("apps.tickets.service.notify_ticket_status_changed") as hook:
            r = self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"})
        self.assertEqual(r.json(), {"ok": True, "status": "testing"})
        t.refresh_from_db()
        self.assertEqual(t.status, "testing")
        hook.assert_called_once()
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_status_changed").exists())
        from apps.notifications.models import Notification

        self.assertTrue(Notification.objects.filter(user=watcher, title__contains="moved to Testing").exists())

    def test_resolving_auto_logs_to_the_dsr(self):
        t = self.make(self.p_open)
        t.set_assignees([self.owner])
        self.login("owner")
        with mock.patch("apps.dsr.service.auto_log_ticket_dsr") as dsr:
            self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "resolved"})
        dsr.assert_called_once()

    def test_invalid_status_is_400_and_changes_nothing(self):
        t = self.make(self.p_open)
        self.login("owner")
        r = self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "bogus"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a valid status", r.json()["detail"])
        t.refresh_from_db()
        self.assertEqual(t.status, "open")

    def test_status_on_an_inaccessible_ticket_is_404(self):
        t = self.make(self.p_hidden)
        self.login("dev")
        self.assertEqual(self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"}).status_code, 404)
        t.refresh_from_db()
        self.assertEqual(t.status, "open")

    def test_status_on_another_companys_ticket_is_404(self):
        t = self.make(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.post_json(f"/ui-api/v1/tickets/{t.pk}/status/", {"status": "testing"}).status_code, 404)

    def test_csrf_is_enforced_on_writes(self):
        t = self.make(self.p_open)
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="owner", password="pass1234")
        body = {"status": "testing"}
        self.assertEqual(strict.post(f"/ui-api/v1/tickets/{t.pk}/status/", body, content_type="application/json").status_code, 403)
        self.assertEqual(strict.delete(f"/ui-api/v1/tickets/{t.pk}/").status_code, 403)

    def test_delete_by_creator_and_admin_but_not_by_a_stranger(self):
        mine = self.make(self.p_open, created_by=self.dev)
        theirs = self.make(self.p_open, created_by=self.owner)
        self.login("dev")
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{theirs.pk}/").status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=theirs.pk).exists())
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{mine.pk}/").json(), {"deleted": mine.key})
        self.assertFalse(Ticket.objects.filter(pk=mine.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_deleted").exists())
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{theirs.pk}/").status_code, 200)

    def test_bulk_delete_skips_what_it_must_and_counts(self):
        ok = self.make(self.p_open, created_by=self.dev)
        not_mine = self.make(self.p_open, created_by=self.owner)
        hidden = self.make(self.p_hidden, created_by=self.dev)
        foreign = self.make(self.p_foreign)
        self.login("dev")
        ids = [ok.pk, not_mine.pk, hidden.pk, foreign.pk, 99999, "x"]
        r = self.post_json("/ui-api/v1/tickets/bulk-delete/", {"ids": ids})
        self.assertEqual(r.json(), {"deleted": 1, "skipped": 5})
        self.assertEqual(Ticket.objects.filter(pk__in=[not_mine.pk, hidden.pk, foreign.pk]).count(), 3)

    def test_bulk_delete_needs_ids(self):
        self.login("owner")
        self.assertEqual(self.post_json("/ui-api/v1/tickets/bulk-delete/", {"ids": []}).status_code, 400)
        self.assertEqual(self.post_json("/ui-api/v1/tickets/bulk-delete/", {}).status_code, 400)


class TicketRobustnessTest(Base):
    url = "/ui-api/v1/tickets/"

    def test_a_non_numeric_product_or_assignee_filter_is_ignored_not_a_500(self):
        self.make(self.p_open, "a")
        self.login("owner")
        for params in ({"product": "abc"}, {"assigned": "abc"}, {"product": "1; DROP"}):
            r = self.client.get(self.url, params)
            self.assertEqual(r.status_code, 200, params)
            self.assertEqual(r.json()["page"]["count"], 1)

    def test_bulk_delete_counts_each_ticket_once_and_caps_the_batch(self):
        t = self.make(self.p_open, created_by=self.owner)
        self.login("owner")
        r = self.client.post("/ui-api/v1/tickets/bulk-delete/", {"ids": [t.pk, t.pk, str(t.pk)]}, content_type="application/json")
        self.assertEqual(r.json(), {"deleted": 1, "skipped": 0})
        r = self.client.post("/ui-api/v1/tickets/bulk-delete/", {"ids": list(range(1, 2001))}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["deleted"] + r.json()["skipped"], 500)

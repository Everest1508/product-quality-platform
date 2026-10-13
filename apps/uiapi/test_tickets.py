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

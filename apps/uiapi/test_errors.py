from django.test import Client

from apps.dashboards.models import ActivityLog
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.products.models import ProductVersion
from apps.tickets.models import Ticket
from apps.uiapi.test_tickets import Base, member


class ErrorsBase(Base):
    def err(self, product, title="Boom", **kw):
        kw.setdefault("fingerprint", title)
        return ErrorGroup.objects.create(company=product.company, product=product, title=title, **kw)


class ErrorListApiTest(ErrorsBase):
    url = "/ui-api/v1/errors/"

    def test_shape(self):
        g = self.err(self.p_open, "Boom", severity="high", occurrence_count=7)
        ErrorOccurrence.objects.create(company=self.acme, error_group=g)
        self.login("dev")
        data = self.client.get(self.url).json()
        item = data["items"][0]
        self.assertEqual((item["id"], item["title"], item["severity"], item["status"]), (g.pk, "Boom", "high", "open"))
        self.assertEqual(item["product"], {"id": self.p_open.pk, "name": "Open"})
        self.assertEqual(item["url"], f"/products/{self.p_open.pk}/errors/{g.pk}/")
        self.assertEqual(item["occurrence_count"], 7)
        self.assertEqual(item["trend"]["total"], 1)
        self.assertFalse(item["can_delete"])
        self.assertEqual((data["page"]["count"], data["open_count"], data["regressed_count"]), (1, 1, 0))

    def test_only_accessible_products(self):
        self.err(self.p_open, "mine")
        self.err(self.p_hidden, "secret")
        self.err(self.p_foreign, "foreign")
        self.login("dev")
        self.assertEqual([i["title"] for i in self.client.get(self.url).json()["items"]], ["mine"])
        self.login("owner")
        self.assertEqual(self.client.get(self.url).json()["page"]["count"], 2)

    def test_filters_and_counts(self):
        self.err(self.p_open, "a-open", severity="low")
        self.err(self.p_open, "b-done", status="resolved", severity="high")
        self.err(self.p_hidden, "c-back", regression_count=1)
        self.login("owner")
        titles = lambda q: [i["title"] for i in self.client.get(self.url + q).json()["items"]]
        self.assertEqual(titles("?status=resolved"), ["b-done"])
        self.assertEqual(titles("?severity=low"), ["a-open"])
        self.assertEqual(titles("?q=back"), ["c-back"])
        self.assertEqual(titles(f"?product={self.p_hidden.pk}"), ["c-back"])
        data = self.client.get(self.url + "?regressed=1").json()
        self.assertEqual([i["title"] for i in data["items"]], ["c-back"])
        self.assertEqual(data["regressed_count"], 1)
        self.assertEqual(self.client.get(self.url + "?status=resolved").json()["open_count"], 0)

    def test_flags(self):
        v = ProductVersion.objects.create(company=self.acme, product=self.p_open, version_string="2.0", is_current=True)
        self.err(self.p_open, "x", first_version=v, regression_count=2)
        self.login("owner")
        item = self.client.get(self.url).json()["items"][0]
        self.assertTrue(item["is_regression"])
        self.assertEqual(item["new_in_release"], "2.0")

    def test_product_scope(self):
        self.err(self.p_open, "in")
        self.err(self.p_hidden, "out")
        self.login("owner")
        r = self.client.get(self.url + f"?scope=product&product={self.p_open.pk}").json()
        self.assertEqual([i["title"] for i in r["items"]], ["in"])
        self.login("dev")
        self.assertEqual(self.client.get(self.url + f"?scope=product&product={self.p_hidden.pk}").status_code, 404)
        self.assertEqual(self.client.get(self.url + f"?scope=product&product={self.p_foreign.pk}").status_code, 404)

    def test_sort_and_paging(self):
        for i in range(27):
            self.err(self.p_open, f"e{i:02}", occurrence_count=i + 1)
        self.login("owner")
        data = self.client.get(self.url + "?sort=-count&page=2").json()
        self.assertEqual((data["page"]["num_pages"], len(data["items"])), (2, 2))
        self.assertEqual(self.client.get(self.url + "?sort=-count").json()["items"][0]["occurrence_count"], 27)

    def test_meta(self):
        self.login("dev")
        meta = self.client.get(self.url + "meta/").json()
        self.assertEqual([p["name"] for p in meta["products"]], ["Open"])
        self.assertEqual(meta["statuses"][0], ["open", "Open"])
        self.assertEqual(meta["severities"][0], ["critical", "Critical"])


class ErrorCreateApiTest(ErrorsBase):
    url = "/ui-api/v1/errors/"

    def body(self, **over):
        return {"product": self.p_open.pk, "title": "Kaput", "error_type": "TypeError", "severity": "high",
                "stacktrace": "", "environment": "production", "page": "", **over}

    def test_create(self):
        self.login("dev")
        r = self.client.post(self.url, self.body(), content_type="application/json")
        self.assertEqual(r.status_code, 201)
        g = ErrorGroup.objects.get(title="Kaput")
        self.assertEqual(r.json()["url"], f"/products/{self.p_open.pk}/errors/{g.pk}/")
        self.assertEqual(g.occurrences.count(), 1)
        self.assertTrue(ActivityLog.objects.filter(event_type="error_created").exists())

    def test_product_must_be_accessible(self):
        self.login("dev")
        for p in (self.p_hidden, self.p_foreign):
            r = self.client.post(self.url, self.body(product=p.pk), content_type="application/json")
            self.assertEqual(r.status_code, 400)
            self.assertIn("product", r.json()["errors"])
        self.assertFalse(ErrorGroup.objects.exists())

    def test_validation_and_csrf(self):
        self.login("dev")
        r = self.client.post(self.url, self.body(title=""), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.json()["errors"])
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="dev", password="pass1234")
        self.assertEqual(strict.post(self.url, self.body(), content_type="application/json").status_code, 403)


class ErrorDetailApiTest(ErrorsBase):
    def url(self, g, tail=""):
        return f"/ui-api/v1/errors/{g.pk}/{tail}"

    def test_shape(self):
        v = ProductVersion.objects.create(company=self.acme, product=self.p_open, version_string="1.0")
        g = self.err(self.p_open, "Boom", first_version=v, affected_user_count=3)
        ErrorOccurrence.objects.create(company=self.acme, error_group=g, version=v, stacktrace="trace", user_ref="u1")
        t = self.make(self.p_open, "Fix it", linked_error_group=g)
        self.make(self.p_hidden, "elsewhere")
        self.login("dev")
        data = self.client.get(self.url(g)).json()
        e = data["error"]
        self.assertEqual((e["title"], e["affected_user_count"], e["first_version"]), ("Boom", 3, "1.0"))
        self.assertFalse(e["can_delete"])
        occ = data["occurrences"][0]
        self.assertEqual((occ["stacktrace"], occ["user_ref"], occ["version"]), ("trace", "u1", "1.0"))
        self.assertEqual(data["trend"]["days"], 30)
        self.assertEqual(len(data["trend"]["bars"]), 30)
        self.assertEqual(data["trend"]["by_version"], [{"version": "1.0", "count": 1}])
        self.assertEqual([x["key"] for x in data["linked_tickets"]], [t.key])
        self.assertEqual(data["statuses"][0], ["open", "Open"])

    def test_linked_tickets_respect_product_access(self):
        g = self.err(self.p_open)
        self.make(self.p_hidden, "secret", linked_error_group=g)
        self.login("dev")
        self.assertEqual(self.client.get(self.url(g)).json()["linked_tickets"], [])

    def test_inaccessible_and_foreign_are_404(self):
        hidden, foreign = self.err(self.p_hidden), self.err(self.p_foreign)
        self.login("dev")
        self.assertEqual(self.client.get(self.url(hidden)).status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(self.url(foreign)).status_code, 404)


class ErrorActionsApiTest(ErrorsBase):
    def post(self, g, action, body=None):
        return self.client.post(f"/ui-api/v1/errors/{g.pk}/{action}/", body or {}, content_type="application/json")

    def test_status(self):
        g = self.err(self.p_open)
        self.login("dev")
        r = self.post(g, "status", {"status": "resolved"})
        self.assertEqual(r.json()["error"]["status"], "resolved")
        self.assertEqual(r.json()["message"], "Error group resolved.")
        self.assertEqual(self.post(g, "status", {"status": "bogus"}).status_code, 400)

    def test_status_needs_access(self):
        hidden = self.err(self.p_hidden)
        self.login("dev")
        self.assertEqual(self.post(hidden, "status", {"status": "resolved"}).status_code, 404)
        hidden.refresh_from_db()
        self.assertEqual(hidden.status, "open")

    def test_convert_to_ticket(self):
        g = self.err(self.p_open, severity="critical")
        self.login("dev")
        r = self.post(g, "convert-to-ticket")
        self.assertEqual(r.status_code, 200)
        t = Ticket.objects.get(linked_error_group=g)
        self.assertEqual(r.json()["ticket"]["key"], t.key)
        self.assertEqual([x["key"] for x in r.json()["linked_tickets"]], [t.key])

    def test_convert_needs_access(self):
        self.login("dev")
        self.assertEqual(self.post(self.err(self.p_hidden), "convert-to-ticket").status_code, 404)
        self.assertFalse(Ticket.objects.exists())

    def test_delete_is_for_owners_and_admins(self):
        g = self.err(self.p_open)
        self.login("dev")
        r = self.client.delete(f"/ui-api/v1/errors/{g.pk}/")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(ErrorGroup.objects.filter(pk=g.pk).exists())
        self.login("owner")
        r = self.client.delete(f"/ui-api/v1/errors/{g.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ErrorGroup.objects.filter(pk=g.pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="error_deleted").exists())

    def test_delete_foreign_is_404(self):
        foreign = self.err(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.client.delete(f"/ui-api/v1/errors/{foreign.pk}/").status_code, 404)
        self.assertTrue(ErrorGroup.objects.filter(pk=foreign.pk).exists())


class BadInputTest(ErrorsBase):
    def test_odd_input_is_a_400_or_ignored_never_a_500(self):
        g = self.err(self.p_open)
        self.login("owner")
        self.assertEqual(self.client.get("/ui-api/v1/errors/?product=%C2%B2").status_code, 200)
        post = lambda url, body: self.client.post(url, body, content_type="application/json")
        self.assertEqual(post(f"/ui-api/v1/errors/{g.pk}/status/", {"status": ["a"]}).status_code, 400)
        self.assertEqual(post(f"/ui-api/v1/errors/{g.pk}/status/", [1]).status_code, 400)
        self.assertEqual(post("/ui-api/v1/errors/", [1]).status_code, 400)
        self.assertEqual(post("/ui-api/v1/tickets/", [1]).status_code, 400)

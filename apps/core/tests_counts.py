"""The numbers in the sidebar, the page headers and the product cards must agree."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.ingestion.models import ErrorGroup
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


class OpenCountsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("own", "o@t.local", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.p1 = Product.objects.create(name="One", slug="one", company=self.company)
        self.p2 = Product.objects.create(name="Two", slug="two", company=self.company)
        ProductAccess.objects.create(company=self.company, product=self.p1, user=self.dev)
        for product, status in [(self.p1, "open"), (self.p1, "in_progress"), (self.p1, "resolved"),
                                (self.p2, "open"), (self.p2, "closed")]:
            Ticket.objects.create(company=self.company, product=product, title=f"t {status}", status=status, created_by=self.owner)
        for product, status in [(self.p1, "open"), (self.p1, "ignored"), (self.p2, "open"), (self.p2, "resolved")]:
            ErrorGroup.objects.create(company=self.company, product=product, fingerprint=f"{product.pk}{status}", title=f"e {status}", status=status)

    def login(self, user):
        self.client.login(username=user.username, password="pass1234")

    def api(self, **params):
        return self.client.get("/ui-api/v1/tickets/", params).json()

    def sidebar_open_tickets(self):
        return self.client.get("/ui-api/v1/bootstrap/").json()["counts"]["open_tickets"]

    def test_ticket_list_header_and_sidebar_agree_for_an_owner(self):
        self.login(self.owner)
        data = self.api()
        self.assertEqual((data["page"]["count"], data["open_count"]), (5, 3))
        self.assertEqual(self.sidebar_open_tickets(), 3)

    def test_counts_only_cover_products_the_person_can_open(self):
        self.login(self.dev)
        data = self.api()
        self.assertEqual((data["page"]["count"], data["open_count"]), (3, 2))
        self.assertEqual(self.sidebar_open_tickets(), 2)

    def test_a_filter_changes_both_numbers_in_the_header(self):
        self.login(self.owner)
        data = self.api(status="resolved")
        self.assertEqual((data["page"]["count"], data["open_count"]), (1, 0))

    def test_kanban_header_matches_the_list(self):
        self.login(self.owner)
        data = self.api(view="board")
        self.assertEqual((data["total"], data["open_count"]), (5, 3))

    def test_error_list_header_and_sidebar_agree(self):
        self.login(self.owner)
        data = self.client.get("/ui-api/v1/errors/").json()
        self.assertEqual((data["page"]["count"], data["open_count"]), (4, 2))
        self.assertEqual(self.client.get("/ui-api/v1/bootstrap/").json()["counts"]["open_errors"], 2)


    def test_product_page_headers_count_open_work(self):
        self.login(self.owner)
        data = self.api(scope="product", product=self.p1.pk)
        self.assertEqual((data["page"]["count"], data["open_count"]), (3, 2))
        data = self.client.get("/ui-api/v1/errors/", {"scope": "product", "product": self.p1.pk}).json()
        self.assertEqual((data["page"]["count"], data["open_count"]), (2, 1))

    def test_product_cards_say_open(self):
        self.login(self.owner)
        data = self.client.get("/ui-api/v1/products/").json()
        self.assertEqual((data["summary"]["open_errors"], data["summary"]["open_tickets"]), (2, 3))


class HomeAndReportsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("own", "o@t.local", "pass1234", first_name="Olive")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.client.login(username="own", password="pass1234")

    def test_home_carries_the_name_and_a_quote_and_the_quote_endpoint_changes_it(self):
        from apps.dashboards.quotes import QUOTES

        data = self.client.get("/ui-api/v1/dashboard/").json()
        self.assertEqual((data["first_name"], data["company"]), ("Olive", "Acme"))
        self.assertIn(data["quote"], QUOTES)
        res = self.client.get("/ui-api/v1/dashboard/quote/", {"current": QUOTES[0]})
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(res.json()["quote"], QUOTES[0])

    def test_quote_needs_a_workspace(self):
        from django.test import Client

        self.assertIn(Client().get("/ui-api/v1/dashboard/quote/").status_code, (401, 403))

    def test_reports_shows_tiles_and_charts(self):
        from apps.dashboards.service import log_activity

        log_activity(self.company, "ticket_created", "A ticket", actor=self.owner)
        res = self.client.get("/ui-api/v1/reports/")
        self.assertEqual(res.status_code, 200)
        d = res.json()
        self.assertEqual(len(d["daily_bars"]), 1)
        self.assertIn("resolution_rate", d)
        kpis = {k["key"]: k for k in d["kpis"]}
        self.assertEqual(kpis["tickets_created"]["value"], 1)
        self.assertEqual(kpis["tickets_created"]["dir"], "up")

    def test_reports_compare_with_the_period_before(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.dashboards.models import ActivityLog
        from apps.dashboards.service import log_activity

        today = timezone.localdate()
        for _ in range(2):
            log_activity(self.company, "ticket_created", "Earlier", actor=self.owner)
        ActivityLog.objects.update(created_at=timezone.now() - timedelta(days=1))
        log_activity(self.company, "ticket_created", "Now", actor=self.owner)
        res = self.client.get("/ui-api/v1/reports/", {"start_date": today.isoformat(), "end_date": today.isoformat()})
        tile = {k["key"]: k for k in res.json()["kpis"]}["tickets_created"]
        self.assertEqual((tile["value"], tile["before"], tile["dir"], tile["pct"]), (1, 2, "down", 50))

    def test_report_range_presets(self):
        labels = [p["label"] for p in self.client.get("/ui-api/v1/reports/").json()["presets"]]
        self.assertIn("Last 30 days", labels)
        self.assertIn("This month", labels)

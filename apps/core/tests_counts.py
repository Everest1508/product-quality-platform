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

    def test_ticket_list_header_and_sidebar_agree_for_an_owner(self):
        self.login(self.owner)
        res = self.client.get(reverse("tickets:ticket_list"))
        self.assertContains(res, "5 tickets · 3 open")
        self.assertEqual(res.context["nav_open_tickets"], 3)

    def test_counts_only_cover_products_the_person_can_open(self):
        self.login(self.dev)
        res = self.client.get(reverse("tickets:ticket_list"))
        self.assertContains(res, "3 tickets · 2 open")
        self.assertEqual(res.context["nav_open_tickets"], 2)

    def test_a_filter_changes_both_numbers_in_the_header(self):
        self.login(self.owner)
        res = self.client.get(reverse("tickets:ticket_list"), {"status": "resolved"})
        self.assertContains(res, "1 ticket · 0 open")

    def test_kanban_header_matches_the_list(self):
        self.login(self.owner)
        res = self.client.get(reverse("tickets:ticket_board"))
        self.assertContains(res, "5 tickets · 3 open")

    def test_error_list_header_and_sidebar_agree(self):
        self.login(self.owner)
        res = self.client.get(reverse("errors:error_list"))
        self.assertContains(res, "4 groups · 2 open")
        self.assertEqual(res.context["nav_open_errors"], 2)

    def test_htmx_refresh_carries_the_open_count(self):
        self.login(self.owner)
        res = self.client.get(reverse("tickets:ticket_list"), HTTP_HX_REQUEST="true")
        self.assertContains(res, "5 tickets · 3 open")

    def test_product_page_headers_count_open_work(self):
        self.login(self.owner)
        res = self.client.get(reverse("products:product_tickets", kwargs={"pk": self.p1.pk}))
        self.assertContains(res, "3 tickets · 2 open")
        res = self.client.get(reverse("products:product_errors", kwargs={"pk": self.p1.pk}))
        self.assertContains(res, "2 groups · 1 open")

    def test_product_cards_say_open(self):
        self.login(self.owner)
        res = self.client.get(reverse("products:product_list"))
        self.assertContains(res, "Open errors")
        self.assertContains(res, "Open tickets")


class HomeAndReportsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("own", "o@t.local", "pass1234", first_name="Olive")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.client.login(username="own", password="pass1234")

    def test_home_has_a_greeting_a_clock_and_a_quote(self):
        res = self.client.get(reverse("dashboards:index"))
        self.assertContains(res, 'class="hero"')
        self.assertContains(res, "Olive")
        self.assertContains(res, 'id="dash-quote"')
        self.assertContains(res, "heroClock(")

    def test_quote_endpoint_returns_a_fragment_that_differs_from_the_current_one(self):
        from apps.dashboards.quotes import QUOTES

        res = self.client.get(reverse("dashboards:quote"), {"current": QUOTES[0]})
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, "<html")
        self.assertNotContains(res, f">{QUOTES[0]}<")

    def test_quote_needs_a_workspace(self):
        from django.test import Client

        res = Client().get(reverse("dashboards:quote"))
        self.assertEqual(res.status_code, 302)

    def test_reports_shows_tiles_and_charts(self):
        from apps.dashboards.service import log_activity

        log_activity(self.company, "ticket_created", "A ticket", actor=self.owner)
        res = self.client.get(reverse("dashboards:reports"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'class="rk-row"')
        self.assertContains(res, "Day by day")
        self.assertContains(res, "How much got finished")
        kpis = {k["key"]: k for k in res.context["kpis"]}
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
        res = self.client.get(reverse("dashboards:reports"), {"start_date": today.isoformat(), "end_date": today.isoformat()})
        tile = {k["key"]: k for k in res.context["kpis"]}["tickets_created"]
        self.assertEqual((tile["value"], tile["before"], tile["dir"], tile["pct"]), (1, 2, "down", 50))

    def test_report_range_buttons_render(self):
        res = self.client.get(reverse("dashboards:reports"))
        self.assertContains(res, "Last 30 days")
        self.assertContains(res, "This month")

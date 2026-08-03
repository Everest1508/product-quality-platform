from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import (
    get_admin_dashboard_data,
    get_product_dashboard_data,
    get_user_dashboard_data,
    log_activity,
)
from apps.feedback.models import Survey, SurveyResponse
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


class DashboardServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)

    def test_admin_dashboard_data(self):
        Ticket.objects.create(
            company=self.company, product=self.product,
            title="Bug", status="open",
        )
        ErrorGroup.objects.create(
            company=self.company, product=self.product,
            fingerprint="abc", title="Error", occurrence_count=5,
        )

        data = get_admin_dashboard_data(self.company)
        self.assertEqual(data["member_count"], 1)
        self.assertEqual(data["open_errors"], 1)
        self.assertEqual(data["open_tickets"], 1)
        self.assertIn("activity", data)

    def test_admin_dashboard_empty(self):
        data = get_admin_dashboard_data(self.company)
        self.assertEqual(data["member_count"], 1)
        self.assertEqual(data["open_errors"], 0)
        self.assertEqual(data["open_tickets"], 0)

    def test_product_dashboard_data(self):
        for i in range(5):
            ErrorGroup.objects.create(
                company=self.company, product=self.product,
                fingerprint=f"fp{i}", title=f"Error {i}",
                severity="critical" if i < 2 else "low",
            )
        Ticket.objects.create(
            company=self.company, product=self.product,
            title="Bug", status="open",
        )
        survey = Survey.objects.create(
            company=self.company, product=self.product,
            name="NPS", survey_type="nps", status="active",
        )
        for score in [8, 9, 10]:
            SurveyResponse.objects.create(
                survey=survey, company=self.company, score=score,
            )

        data = get_product_dashboard_data(self.company, self.product)
        self.assertEqual(data["total_errors"], 5)
        self.assertEqual(data["open_errors"], 5)
        self.assertEqual(data["total_tickets"], 1)
        self.assertEqual(data["total_responses"], 3)
        self.assertEqual(data["avg_score"], 9.0)
        self.assertEqual(len(data["errors_by_day"]), 30)
        self.assertEqual(len(data["ticket_burndown"]), 30)
        self.assertIsNotNone(data["uptime_percentage"])

    def test_log_activity(self):
        entry = log_activity(
            company=self.company,
            event_type="error_captured",
            title="New error captured",
            actor=self.user,
        )
        self.assertEqual(ActivityLog.objects.count(), 1)
        self.assertEqual(entry.company, self.company)
        self.assertEqual(entry.event_type, "error_captured")


class UserDashboardServiceTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.product_a = Product.objects.create(name="App A", slug="app-a", company=self.company)
        self.product_b = Product.objects.create(name="App B", slug="app-b", company=self.company)
        ProductAccess.objects.create(product=self.product_a, user=self.dev, company=self.company)

        self.error_a = ErrorGroup.objects.create(
            company=self.company, product=self.product_a,
            fingerprint="fp-a", title="Err A", severity="high",
        )
        self.error_b = ErrorGroup.objects.create(
            company=self.company, product=self.product_b,
            fingerprint="fp-b", title="Err B", severity="critical",
        )
        Ticket.objects.create(company=self.company, product=self.product_a, title="T A", status="open")
        Ticket.objects.create(company=self.company, product=self.product_b, title="T B", status="open")

    def test_developer_only_sees_allocated_product(self):
        data = get_user_dashboard_data(self.dev, self.company)
        self.assertFalse(data["is_privileged"])
        card_ids = {c["product"].id for c in data["product_cards"]}
        self.assertEqual(card_ids, {self.product_a.pk})
        self.assertEqual(data["open_errors"], 1)
        self.assertEqual(data["open_tickets"], 1)

    def test_owner_sees_company_wide(self):
        data = get_user_dashboard_data(self.owner, self.company)
        self.assertTrue(data["is_privileged"])
        card_ids = {c["product"].id for c in data["product_cards"]}
        self.assertEqual(card_ids, {self.product_a.pk, self.product_b.pk})
        self.assertEqual(data["open_errors"], 2)
        self.assertEqual(data["open_tickets"], 2)
        self.assertIn("member_count", data)
        self.assertIn("role_breakdown", data)

    def test_my_work_scoped_to_user(self):
        assigned = Ticket.objects.create(
            company=self.company, product=self.product_a,
            title="Mine", status="in_progress", assigned_to=self.dev,
        )
        Ticket.objects.create(
            company=self.company, product=self.product_b,
            title="Not mine", status="open", assigned_to=self.owner,
        )
        data = get_user_dashboard_data(self.dev, self.company)
        self.assertEqual([t.pk for t in data["my_work"]], [assigned.pk])
        self.assertEqual(data["my_work_count"], 1)

    def test_attention_scoped_to_allocated_product(self):
        Ticket.objects.create(
            company=self.company, product=self.product_b,
            title="Stale in B", status="open",
            updated_at=timezone.now() - timedelta(days=10),
        )
        data = get_user_dashboard_data(self.dev, self.company)
        self.assertEqual(len(data["attention"]["stale_tickets"]), 0)
        error_ids = [e.pk for e in data["attention"]["critical_errors"]]
        self.assertIn(self.error_a.pk, error_ids)
        self.assertNotIn(self.error_b.pk, error_ids)

    def test_no_products_for_user_without_access(self):
        other = User.objects.create_user("newbie", "newbie@test.com", "pass1234")
        Membership.objects.create(user=other, company=self.company, role="viewer")
        data = get_user_dashboard_data(other, self.company)
        self.assertEqual(data["product_cards"], [])
        self.assertEqual(data["open_errors"], 0)
        self.assertEqual(data["open_tickets"], 0)


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")

    def test_dashboard_page(self):
        response = self.client.get(reverse("dashboards:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_privileged"])

    def test_dashboard_htmx(self):
        response = self.client.get(
            reverse("dashboards:index"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_developer_scoped(self):
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        product_a = Product.objects.create(name="App A", slug="app-a", company=self.company)
        Product.objects.create(name="App B", slug="app-b", company=self.company)
        ProductAccess.objects.create(product=product_a, user=dev, company=self.company)

        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("dashboards:index"))
        self.assertEqual(response.status_code, 200)
        card_ids = {c["product"].id for c in response.context["product_cards"]}
        self.assertEqual(card_ids, {product_a.pk})
        self.assertFalse(response.context["is_privileged"])
        content = response.content.decode()
        self.assertNotIn("Team Breakdown", content)

    def test_dashboard_no_products_empty_state(self):
        viewer = User.objects.create_user("viewer", "viewer@test.com", "pass1234")
        Membership.objects.create(user=viewer, company=self.company, role="viewer")
        self.client.login(username="viewer", password="pass1234")
        response = self.client.get(reverse("dashboards:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product_cards"], [])
        self.assertIn("You don't have access to any products yet", response.content.decode())


class ProductDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_product_dashboard_page(self):
        response = self.client.get(
            reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_product_dashboard_htmx(self):
        response = self.client.get(
            reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk}),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)

    def test_cannot_view_other_company_product(self):
        company2 = Company.objects.create(name="Beta", slug="beta")
        other_product = Product.objects.create(name="Other", slug="other", company=company2)
        response = self.client.get(
            reverse("dashboards:product_dashboard", kwargs={"product_pk": other_product.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_view_product_without_access(self):
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(
            reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_can_view_allocated_product(self):
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        ProductAccess.objects.create(product=self.product, user=dev, company=self.company)
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(
            reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk})
        )
        self.assertEqual(response.status_code, 200)

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import get_admin_dashboard_data, get_product_dashboard_data, log_activity
from apps.feedback.models import Survey, SurveyResponse
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.products.models import Product
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


class AdminDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")

    def test_admin_dashboard_page(self):
        response = self.client.get(reverse("dashboards:admin_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_admin_dashboard_htmx(self):
        response = self.client.get(
            reverse("dashboards:admin_dashboard"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)


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

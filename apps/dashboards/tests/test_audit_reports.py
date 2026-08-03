from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import get_summary_report, log_activity
from apps.products.models import Product, ProductAccess

User = get_user_model()


class AuditLogViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")

    def test_owner_can_view_audit_log(self):
        self.client.login(username="owner", password="pass1234")
        log_activity(self.company, "ticket_created", "Ticket #1 created", actor=self.owner)
        response = self.client.get(reverse("dashboards:audit_log"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertIn("Ticket #1 created", response.content.decode())

    def test_developer_forbidden(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("dashboards:audit_log"))
        self.assertEqual(response.status_code, 403)

    def test_audit_htmx(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("dashboards:audit_log"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)

    def test_filter_by_event_type(self):
        self.client.login(username="owner", password="pass1234")
        log_activity(self.company, "ticket_created", "Ticket #1 created", actor=self.owner)
        log_activity(self.company, "error_captured", "Err captured", actor=self.owner)
        response = self.client.get(reverse("dashboards:audit_log"), {"type": "error_captured"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertIn("Err captured", response.content.decode())
        self.assertNotIn("Ticket #1 created", response.content.decode())

    def test_filter_by_date_range(self):
        self.client.login(username="owner", password="pass1234")
        old = log_activity(self.company, "ticket_created", "Old event", actor=self.owner)
        ActivityLog.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        today = timezone.localdate()
        response = self.client.get(reverse("dashboards:audit_log"), {
            "from": (today - timedelta(days=2)).isoformat(),
            "to": today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 0)


class ReportsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)

    def test_owner_can_view_reports(self):
        self.client.login(username="owner", password="pass1234")
        log_activity(self.company, "ticket_created", "Ticket #1 created", actor=self.owner,
                     metadata={"product_id": self.product.pk})
        response = self.client.get(reverse("dashboards:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tickets_created"], 1)
        self.assertIn("Ticket #1 created", response.content.decode())

    def test_developer_sees_own_report(self):
        self.client.login(username="dev", password="pass1234")
        log_activity(self.company, "ticket_created", "Dev ticket", actor=self.dev,
                     metadata={"product_id": self.product.pk})
        log_activity(self.company, "ticket_created", "Owner ticket", actor=self.owner,
                     metadata={"product_id": self.product.pk})
        response = self.client.get(reverse("dashboards:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "mine")
        self.assertEqual(response.context["tickets_created"], 1)
        self.assertIn("Dev ticket", response.content.decode())
        self.assertNotIn("Owner ticket", response.content.decode())

    def test_reports_date_range_param(self):
        self.client.login(username="owner", password="pass1234")
        log_activity(self.company, "ticket_created", "Ticket #1 created", actor=self.owner)
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        response = self.client.get(reverse("dashboards:reports"), {
            "start_date": yesterday.isoformat(),
            "end_date": today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["tickets_created"], 1)
        self.assertEqual(response.context["start_date"], yesterday)


class SummaryReportServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        from apps.products.models import Product
        self.product = Product.objects.create(name="App", slug="app", company=self.company)

    def test_summary_counts(self):
        log_activity(self.company, "ticket_created", "Ticket #1 created",
                     metadata={"product_id": self.product.pk})
        log_activity(self.company, "ticket_status_changed", "T1 resolved",
                     metadata={"product_id": self.product.pk, "from": "open", "to": "resolved"})
        log_activity(self.company, "ticket_status_changed", "T2 closed",
                     metadata={"product_id": self.product.pk, "from": "assigned", "to": "closed"})
        log_activity(self.company, "ticket_status_changed", "T3 in progress",
                     metadata={"product_id": self.product.pk, "from": "assigned", "to": "in_progress"})
        log_activity(self.company, "error_captured", "Err captured",
                     metadata={"product_id": self.product.pk})
        log_activity(self.company, "error_resolved", "Err resolved",
                     metadata={"product_id": self.product.pk})
        log_activity(self.company, "feedback_received", "FB", metadata={"product_id": self.product.pk})

        today = timezone.localdate()
        report = get_summary_report(self.company, today, today)

        self.assertEqual(report["tickets_created"], 1)
        self.assertEqual(report["tickets_status_changed"], 3)
        self.assertEqual(report["tickets_resolved"], 1)
        self.assertEqual(report["tickets_closed"], 1)
        self.assertEqual(report["tickets_in_progress"], 1)
        self.assertEqual(report["errors_captured"], 1)
        self.assertEqual(report["errors_resolved"], 1)
        self.assertEqual(report["errors_ignored"], 0)
        self.assertEqual(report["errors_investigated"], 1)
        self.assertEqual(report["feedback_received"], 1)
        self.assertEqual(len(report["daily"]), 1)
        self.assertEqual(len(report["product_rows"]), 1)
        self.assertEqual(report["product_rows"][0]["tickets_created"], 1)
        self.assertEqual(report["product_rows"][0]["tickets_resolved"], 1)
        self.assertEqual(report["product_rows"][0]["errors_captured"], 1)

    def test_summary_date_range_is_inclusive(self):
        log_activity(self.company, "ticket_created", "Today")
        old = log_activity(self.company, "ticket_created", "Old")
        ActivityLog.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=5)
        )

        today = timezone.localdate()
        recent = get_summary_report(self.company, today - timedelta(days=3), today)
        self.assertEqual(recent["tickets_created"], 1)

        past = get_summary_report(
            self.company, today - timedelta(days=10), today - timedelta(days=4)
        )
        self.assertEqual(past["tickets_created"], 1)

    def test_summary_errors_investigated_via_status_change(self):
        log_activity(self.company, "error_status_changed", "Err ignored",
                     metadata={"product_id": self.product.pk, "from": "open", "to": "ignored"})
        today = timezone.localdate()
        report = get_summary_report(self.company, today, today)
        self.assertEqual(report["errors_ignored"], 1)
        self.assertEqual(report["errors_investigated"], 1)

    def test_summary_scoped_to_non_privileged_user(self):
        dev = User.objects.create_user("bob", "bob@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        ProductAccess.objects.create(product=self.product, user=dev, company=self.company)
        other = Product.objects.create(name="Other", slug="other", company=self.company)

        log_activity(self.company, "ticket_created", "By dev",
                     actor=dev, metadata={"product_id": self.product.pk})
        log_activity(self.company, "ticket_created", "By alice",
                     actor=self.user, metadata={"product_id": self.product.pk})
        log_activity(self.company, "ticket_created", "Dev in hidden product",
                     actor=dev, metadata={"product_id": other.pk})

        today = timezone.localdate()
        report = get_summary_report(self.company, today, today, user=dev)

        self.assertEqual(report["scope"], "mine")
        self.assertEqual(report["tickets_created"], 2)
        self.assertEqual(report["total_events"], 2)
        product_slugs = [row["product"].slug for row in report["product_rows"]]
        self.assertEqual(product_slugs, ["app"])
        self.assertEqual(report["product_rows"][0]["tickets_created"], 1)

    def test_summary_company_wide_for_owner(self):
        dev = User.objects.create_user("carol", "carol@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        log_activity(self.company, "ticket_created", "By dev", actor=dev)
        today = timezone.localdate()
        report = get_summary_report(self.company, today, today, user=self.user)
        self.assertEqual(report["scope"], "company")
        self.assertEqual(report["tickets_created"], 1)


class AuditWiringTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="owner", password="pass1234")

    def test_ticket_creation_is_logged(self):
        response = self.client.post(reverse("products:product_ticket_create", kwargs={"pk": self.product.pk}), {
            "title": "Bug on checkout",
            "ticket_type": "bug",
            "priority": "high",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(
                company=self.company,
                event_type="ticket_created",
                title__startswith="Ticket #",
            ).exists()
        )

    def test_product_creation_is_logged(self):
        response = self.client.post(reverse("products:product_create"), {
            "name": "New App",
            "description": "Test",
            "default_environment": "production",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(
                company=self.company,
                event_type="product_created",
                title__contains="New App",
            ).exists()
        )

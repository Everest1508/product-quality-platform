from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import (
    get_admin_dashboard_data,
    get_personal_dashboard_data,
    get_product_dashboard_data,
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


HOME = "/ui-api/v1/dashboard/"


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")

    def test_home_page_serves_the_shell_and_the_data_comes_from_the_api(self):
        r = self.client.get(reverse("dashboards:index"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "uiapi/shell.html")
        self.assertIsNotNone(self.client.get(HOME).json()["needs_attention"])

    def test_dashboard_developer_scoped(self):
        """A developer only sees tickets from products they are allocated to."""
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        product_a = Product.objects.create(name="App A", slug="app-a", company=self.company)
        product_b = Product.objects.create(name="App B", slug="app-b", company=self.company)
        ProductAccess.objects.create(product=product_a, user=dev, company=self.company)
        for product, title in ((product_a, "Mine to see"), (product_b, "Not mine")):
            ticket = Ticket.objects.create(company=self.company, product=product, title=title, status="open", created_by=dev)
            ticket.assignees.add(dev)
        self.client.login(username="dev", password="pass1234")
        data = self.client.get(HOME).json()
        self.assertEqual([t["title"] for t in data["my_tickets"]], ["Mine to see"])
        self.assertIsNone(data["needs_attention"])  # company-wide numbers stay hidden from a non-privileged role

    def test_dashboard_no_products_empty_state(self):
        viewer = User.objects.create_user("viewer", "viewer@test.com", "pass1234")
        Membership.objects.create(user=viewer, company=self.company, role="viewer")
        self.client.login(username="viewer", password="pass1234")
        data = self.client.get(HOME).json()
        self.assertEqual((data["my_tickets"], data["kpis"]["my_tickets"]), ([], 0))


class ProductDashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")
        self.url = f"/ui-api/v1/dashboards/product/{self.product.pk}/"

    def test_page_serves_the_shell_and_the_api_has_the_numbers(self):
        r = self.client.get(reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "uiapi/shell.html")
        d = self.client.get(self.url).json()
        self.assertEqual(d["product"]["name"], "App")
        self.assertEqual(len(d["errors_by_day"]), 30)
        self.assertEqual(len(d["ticket_burndown"]), 30)

    def test_cannot_view_other_company_product(self):
        company2 = Company.objects.create(name="Beta", slug="beta")
        other_product = Product.objects.create(name="Other", slug="other", company=company2)
        for url in (reverse("dashboards:product_dashboard", kwargs={"product_pk": other_product.pk}), f"/ui-api/v1/dashboards/product/{other_product.pk}/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_access_follows_product_access(self):
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        self.client.login(username="dev", password="pass1234")
        page = reverse("dashboards:product_dashboard", kwargs={"product_pk": self.product.pk})
        self.assertEqual(self.client.get(page).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        ProductAccess.objects.create(product=self.product, user=dev, company=self.company)
        self.assertEqual(self.client.get(page).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 200)


class PersonalDashboardTest(TestCase):
    """The home page is personal-first: an employee's own month, not the
    company's error count. Role only decides whether the company-wide numbers
    are added, never whether the personal ones are shown."""

    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.admin = User.objects.create_user("boss", "boss@test.com", "pass1234")
        Membership.objects.create(user=self.admin, company=self.company, role="owner")
        self.client.login(username="dev", password="pass1234")

    def api(self):
        return self.client.get(HOME).json()

    def test_both_dashboard_paths_work(self):
        """LOGIN_REDIRECT_URL used to point at '/dashboard/', which matched no
        route, so every login landed on a 404. The singular path now redirects
        to the real one; both must end on a working page."""
        self.assertEqual(self.client.get("/dashboards/").status_code, 200)
        alias = self.client.get("/dashboard/")
        self.assertEqual(alias.status_code, 302)
        self.assertEqual(alias.url, reverse("dashboards:index"))
        self.assertEqual(self.client.get(alias.url).status_code, 200)

    def test_login_redirect_url_is_a_url_name(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "dashboards:index")

    def test_personal_sections_are_there_for_a_developer(self):
        data = self.api()
        for key in ("attendance", "payroll", "leave", "dsr", "my_tickets", "week", "status", "errors", "kpis"):
            self.assertIn(key, data)

    def test_company_numbers_are_admin_only(self):
        self.assertIsNone(self.api()["needs_attention"])
        self.client.login(username="boss", password="pass1234")
        self.assertIsNotNone(self.api()["needs_attention"])

    def test_leave_approvals_only_for_privileged_roles(self):
        from apps.leave.models import LeavePolicy, LeaveRequest
        from datetime import date

        policy = LeavePolicy.objects.create(company=self.company, name="Casual", max_days_per_year=12)
        LeaveRequest.objects.create(company=self.company, user=self.dev, policy=policy, start_date=date(2026, 11, 2),
                                    end_date=date(2026, 11, 3), days=2, status="pending")
        self.assertIsNone(self.api()["needs_attention"])
        self.client.login(username="boss", password="pass1234")
        self.assertEqual(self.api()["needs_attention"]["leave_to_approve"], 1)

    def test_attendance_reflects_only_my_own_punches(self):
        from datetime import datetime, time, timedelta
        from django.utils import timezone as tz
        from apps.attendance import service as attendance_service
        from apps.attendance.models import AttendanceRecord

        today = tz.localdate()
        at = tz.make_aware(datetime.combine(today, time(9, 0)))
        AttendanceRecord.objects.create(company=self.company, user=self.dev, date=today, check_in=at)
        other = User.objects.create_user("mate", "mate@test.com", "pass1234")
        Membership.objects.create(user=other, company=self.company, role="developer")
        # Longer than the one-day cap an unclosed day is held to, so the comparison holds whatever hour the suite runs at.
        colleague_minutes = 12 * 60
        AttendanceRecord.objects.create(company=self.company, user=other, date=today, check_in=at,
                                        check_out=at + timedelta(minutes=colleague_minutes))
        data = self.api()
        self.assertEqual(data["attendance"]["present_days"], 1)
        record = AttendanceRecord.objects.get(company=self.company, user=self.dev, date=today)
        expected = attendance_service.effective_span_for(record, attendance_service.shift_for(self.company))
        minutes = get_personal_dashboard_data(self.dev, self.company)["attendance"]["worked_minutes"]
        self.assertEqual(minutes, expected)
        self.assertLess(expected, colleague_minutes)
        self.assertEqual(data["attendance"]["state"], "open")

    def test_my_month_total_counts_a_day_i_forgot_to_check_out_of(self):
        """Scoring an unclosed day 0 silently costs the employee the day until an admin notices."""
        from datetime import datetime, time, timedelta
        from django.utils import timezone as tz
        from apps.attendance.models import AttendanceRecord
        from apps.attendance.service import net_minutes_for, shift_for

        today = tz.localdate()
        start = tz.make_aware(datetime.combine(today - timedelta(days=1), time(10, 0)))
        record = AttendanceRecord.objects.create(company=self.company, user=self.dev, date=today - timedelta(days=1), check_in=start)
        record.check_in = tz.now() - timedelta(minutes=300)
        record.save()
        minutes = get_personal_dashboard_data(self.dev, self.company)["attendance"]["worked_minutes"]
        self.assertEqual(minutes, net_minutes_for(record, shift_for(self.company)))
        self.assertGreater(minutes, 0)

    def test_payroll_shows_my_salary_not_a_colleagues(self):
        from datetime import date
        from decimal import Decimal
        from apps.payroll.models import PayrollProfile

        PayrollProfile.objects.create(company=self.company, user=self.dev, effective_from=date(2026, 1, 1),
                                      monthly_salary=Decimal("42000.00"), is_on_payroll=True)
        rich = User.objects.create_user("rich", "rich@test.com", "pass1234")
        Membership.objects.create(user=rich, company=self.company, role="developer")
        PayrollProfile.objects.create(company=self.company, user=rich, effective_from=date(2026, 1, 1),
                                      monthly_salary=Decimal("99000.00"), is_on_payroll=True)
        body = self.client.get(HOME).content.decode()
        self.assertIn("42,000.00", body)
        self.assertNotIn("99,000.00", body)

    def test_not_on_payroll_says_so_rather_than_showing_zero(self):
        p = self.api()["payroll"]
        self.assertEqual((p["on_payroll"], p["has_profile"], p["payslip"]), (False, False, None))

    def test_on_payroll_without_a_generated_slip_is_not_claimed_as_absent(self):
        """'On payroll' is a profile fact. Reading it off the payslip told someone whose admin had not run payroll
        yet that they were not on payroll at all."""
        from datetime import date
        from decimal import Decimal
        from apps.payroll.models import PayrollProfile

        PayrollProfile.objects.create(company=self.company, user=self.dev, effective_from=date(2026, 1, 1),
                                      monthly_salary=Decimal("42000.00"), is_on_payroll=True)
        p = self.api()["payroll"]
        self.assertTrue(p["has_profile"])
        self.assertFalse(p["on_payroll"])
        self.assertEqual(p["monthly_salary"], "42,000.00")

    def test_my_tickets_respect_product_access(self):
        """A ticket in a product the developer cannot see must not surface, even when they are assigned to it."""
        ProductAccess.objects.create(product=self.product, user=self.dev, company=self.company)
        hidden = Product.objects.create(name="Hidden", slug="hidden", company=self.company)
        mine = Ticket.objects.create(company=self.company, product=self.product, title="Mine", status="open", created_by=self.dev)
        mine.assignees.add(self.dev)
        secret = Ticket.objects.create(company=self.company, product=hidden, title="Secret", status="open", created_by=self.dev)
        secret.assignees.add(self.dev)
        data = get_personal_dashboard_data(self.dev, self.company)
        titles = [t.title for t in data["my_tickets"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Secret", titles)
        self.assertEqual(data["my_ticket_count"], 1)
        self.assertEqual([t["title"] for t in self.api()["my_tickets"]], ["Mine"])

    def test_tickets_do_not_leak_across_companies(self):
        elsewhere = Ticket.objects.create(company=self.other, product=None, title="Theirs", status="open", created_by=self.admin)
        elsewhere.assignees.add(self.dev)
        data = get_personal_dashboard_data(self.dev, self.company)
        self.assertEqual(([t.title for t in data["my_tickets"]], data["my_ticket_count"]), ([], 0))

    def test_dsr_hours_cover_only_this_week_and_only_mine(self):
        from datetime import timedelta
        from decimal import Decimal
        from apps.dsr.models import DSREntry

        today = timezone.localdate()
        DSREntry.objects.create(company=self.company, user=self.dev, date=today, task_name="Mine today", hours_spent=Decimal("2.5"))
        mate = User.objects.create_user("mate", "mate@test.com", "pass1234")
        Membership.objects.create(user=mate, company=self.company, role="developer")
        DSREntry.objects.create(company=self.company, user=mate, date=today, task_name="Theirs", hours_spent=Decimal("8.00"))
        DSREntry.objects.create(company=self.company, user=self.dev, date=today - timedelta(days=14), task_name="Last sprint", hours_spent=Decimal("7.00"))
        data = get_personal_dashboard_data(self.dev, self.company)
        self.assertEqual(data["dsr"]["dsr_hours"], Decimal("2.5"))
        self.assertEqual(data["dsr"]["dsr_entries"], 1)
        self.assertNotIn("Theirs", [e.task_name for e in data["dsr"]["dsr_recent"]])
        d = self.api()["dsr"]
        self.assertEqual((d["hours"], d["entries"]), ("2.5", 1))

    def test_punching_from_home_uses_the_attendance_rules(self):
        from apps.attendance.models import AttendanceRecord

        r = self.client.post("/ui-api/v1/attendance/punch/", {}, content_type="application/json")
        self.assertEqual((r.status_code, r.json()["action"], r.json()["ok"]), (200, "checked_in", True))
        self.assertTrue(AttendanceRecord.objects.filter(user=self.dev, company=self.company).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="attendance_checked_in", actor=self.dev).exists())
        self.assertEqual(self.api()["attendance"]["state"], "open")
        again = self.client.post("/ui-api/v1/attendance/punch/", {}, content_type="application/json").json()
        self.assertEqual((again["action"], again["ok"]), ("too_soon", False))

    def test_anonymous_is_redirected_to_login_and_the_api_refuses(self):
        self.client.logout()
        r = self.client.get("/dashboards/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)
        self.assertIn(self.client.get(HOME).status_code, (401, 403))


class UnreadableDecimalTakesDownTheDashboardTest(TestCase):
    """The production 500 behind `InvalidOperation at /dashboards/`.

    A single DecimalField cell that SQLite's converter cannot read fails while
    the cursor is being built, so the page dies before any of the view's own
    logic runs -- there is no query the view can be rewritten to avoid. The audit
    command is the repair path, so that is what this pins.
    """

    def setUp(self):
        from decimal import Decimal

        from django.db import connection

        from apps.payroll.models import PayrollProfile

        self.decimal = Decimal
        self.connection = connection
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")
        self.profile = PayrollProfile.objects.create(
            company=self.company, user=self.user, monthly_salary=self.decimal("50000.00"), is_on_payroll=True,
        )

    def test_the_home_data_raises_on_one_unreadable_salary(self):
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?", [float("inf"), self.profile.pk])
        with self.assertRaises(Exception) as ctx:
            self.client.get(HOME)
        self.assertEqual(type(ctx.exception).__name__, "InvalidOperation")

    def test_audit_decimals_repair_restores_the_home_data(self):
        from io import StringIO

        from django.core.management import call_command

        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?", [float("inf"), self.profile.pk])
        buffer = StringIO()
        call_command("audit_decimals", "--fix", "--set", "0.00", stdout=buffer)
        self.assertIn("Repaired 1 cell", buffer.getvalue())
        self.assertEqual(self.client.get(HOME).status_code, 200)

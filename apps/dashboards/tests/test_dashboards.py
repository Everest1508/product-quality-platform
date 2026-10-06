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
        assigned.assignees.set([self.dev])
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
        """A developer only sees tickets from products they are allocated to."""
        dev = User.objects.create_user("dev", "dev@test.com", "pass1234")
        Membership.objects.create(user=dev, company=self.company, role="developer")
        product_a = Product.objects.create(name="App A", slug="app-a", company=self.company)
        product_b = Product.objects.create(name="App B", slug="app-b", company=self.company)
        ProductAccess.objects.create(product=product_a, user=dev, company=self.company)

        for product, title in ((product_a, "Mine to see"), (product_b, "Not mine")):
            ticket = Ticket.objects.create(
                company=self.company, product=product, title=title,
                status="open", created_by=dev,
            )
            ticket.assignees.add(dev)

        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("dashboards:index"))
        self.assertEqual(response.status_code, 200)
        titles = [t.title for t in response.context["my_tickets"]]
        self.assertEqual(titles, ["Mine to see"])
        self.assertFalse(response.context["is_privileged"])
        content = response.content.decode()
        self.assertNotIn("Team Breakdown", content)
        # Company-wide cards stay hidden from a non-privileged role.
        self.assertNotIn("pd-card pd-company", content)

    def test_dashboard_no_products_empty_state(self):
        viewer = User.objects.create_user("viewer", "viewer@test.com", "pass1234")
        Membership.objects.create(user=viewer, company=self.company, role="viewer")
        self.client.login(username="viewer", password="pass1234")
        response = self.client.get(reverse("dashboards:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["my_tickets"], [])
        self.assertIn("No open tickets assigned to you", response.content.decode())


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


class PersonalDashboardTest(TestCase):
    """The home page is personal-first: an employee's own month, not the
    company's error count. Role only decides whether the company-wide cards
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

    def get(self, path="/dashboards/"):
        # The real page. `/dashboard/` is only a redirect to this (see
        # test_both_dashboard_paths_work).
        return self.client.get(path)

    def test_both_dashboard_paths_work(self):
        """LOGIN_REDIRECT_URL used to point at '/dashboard/', which matched no
        route, so every login landed on a 404. The singular path now redirects
        to the real one; both must end on a working page."""
        self.assertEqual(self.get("/dashboards/").status_code, 200)
        alias = self.get("/dashboard/")
        self.assertEqual(alias.status_code, 302)
        self.assertEqual(alias.url, reverse("dashboards:index"))
        self.assertEqual(self.get(alias.url).status_code, 200)

    def test_login_redirect_url_is_a_url_name(self):
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "dashboards:index")

    def test_login_lands_on_a_working_dashboard(self):
        """The exact failure the old setting caused: a 302 to a dead path."""
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"), {"username": "dev", "password": "pass1234"}
        )
        self.assertEqual(response.status_code, 302)
        landed = self.client.get(response.url, follow=True)
        self.assertEqual(landed.status_code, 200)
        self.assertEqual(landed.redirect_chain[-1][0], reverse("dashboards:index"))

    def test_personal_cards_are_shown_to_a_developer(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        for section in ("today", "pay", "leave", "dsr", "tickets"):
            self.assertContains(response, f"pd-card pd-{section}")

    def test_company_cards_are_admin_only(self):
        self.assertNotContains(self.get(), "pd-card pd-company")
        self.assertNotContains(self.get(), 'class="pd-attn"')

        self.client.login(username="boss", password="pass1234")
        response = self.get()
        self.assertContains(response, 'class="pd-attn"')

    def test_leave_approvals_only_for_privileged_roles(self):
        from apps.leave.models import LeavePolicy, LeaveRequest
        from datetime import date

        policy = LeavePolicy.objects.create(
            company=self.company, name="Casual", max_days_per_year=12
        )
        LeaveRequest.objects.create(
            company=self.company,
            user=self.dev,
            policy=policy,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
            days=2,
            status="pending",
        )
        self.assertNotContains(self.get(), 'class="pd-attn"')

        self.client.login(username="boss", password="pass1234")
        self.assertContains(self.get(), 'class="pd-attn"')

    def test_attendance_reflects_only_my_own_punches(self):
        from datetime import date, datetime, time, timedelta
        from django.utils import timezone as tz
        from apps.attendance import service as attendance_service
        from apps.attendance.models import AttendanceRecord

        today = tz.localdate()
        at = tz.make_aware(datetime.combine(today, time(9, 0)))
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=today, check_in=at
        )
        # A colleague working a full day today must not move my numbers.
        other = User.objects.create_user("mate", "mate@test.com", "pass1234")
        Membership.objects.create(user=other, company=self.company, role="developer")
        # Longer than the one-day cap an unclosed day is held to, so the
        # comparison below holds whatever hour the suite runs at. At exactly 8h
        # it failed every afternoon, once the open day had reached its cap.
        colleague_minutes = 12 * 60
        colleague_out = at + timedelta(minutes=colleague_minutes)
        AttendanceRecord.objects.create(
            company=self.company, user=other, date=today,
            check_in=at, check_out=colleague_out,
        )

        response = self.get()
        self.assertEqual(response.context["attendance"]["present_days"], 1)

        # An unclosed day is counted from check-in and capped at one working day,
        # so it is no longer 0 -- see `attendance.service.effective_span_for`.
        # It is deliberately not compared against a literal: that number depends
        # on the hour the suite happens to run, which is how a test ends up
        # passing for a reason nobody chose.
        record = AttendanceRecord.objects.get(
            company=self.company, user=self.dev, date=today
        )
        expected = attendance_service.effective_span_for(
            record, attendance_service.shift_for(self.company)
        )
        self.assertEqual(
            response.context["attendance"]["worked_minutes"], expected
        )
        # The isolation this test exists for: the colleague's full day is absent,
        # so the total is nowhere near their hours plus mine.
        self.assertLess(expected, colleague_minutes)
        self.assertContains(response, "Punch out")

    def test_my_month_total_counts_a_day_i_forgot_to_check_out_of(self):
        """The whole reason an unclosed day is worth anything.

        Scoring it 0 is not neutral: it silently costs the employee the day
        until an admin notices, which is the case nobody notices.
        """
        from datetime import date, datetime, time, timedelta
        from django.utils import timezone as tz
        from apps.attendance.models import AttendanceRecord
        from apps.attendance.service import net_minutes_for, shift_for

        today = tz.localdate()
        start = tz.make_aware(
            datetime.combine(today - timedelta(days=1), time(10, 0))
        )
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev,
            date=today - timedelta(days=1), check_in=start,
        )
        record.check_in = tz.now() - timedelta(minutes=300)
        record.save()

        response = self.get()
        self.assertEqual(
            response.context["attendance"]["worked_minutes"],
            net_minutes_for(record, shift_for(self.company)),
        )
        self.assertGreater(response.context["attendance"]["worked_minutes"], 0)

    def test_payroll_shows_my_salary_not_a_colleagues(self):
        from datetime import date
        from decimal import Decimal
        from apps.payroll.models import PayrollProfile

        PayrollProfile.objects.create(
            company=self.company,
            user=self.dev,
            effective_from=date(2026, 1, 1),
            monthly_salary=Decimal("42000.00"),
            is_on_payroll=True,
        )
        rich = User.objects.create_user("rich", "rich@test.com", "pass1234")
        Membership.objects.create(user=rich, company=self.company, role="developer")
        PayrollProfile.objects.create(
            company=self.company,
            user=rich,
            effective_from=date(2026, 1, 1),
            monthly_salary=Decimal("99000.00"),
            is_on_payroll=True,
        )

        body = self.get().content.decode()
        self.assertIn("42,000.00", body)
        self.assertNotIn("99,000.00", body)

    def test_not_on_payroll_says_so_rather_than_showing_zero(self):
        self.assertContains(self.get(), "not on payroll")

    def test_on_payroll_without_a_generated_slip_is_not_claimed_as_absent(self):
        """Regression: 'on payroll' is a profile fact. Reading it off the
        payslip told someone whose admin had not run payroll yet that they
        were not on payroll at all."""
        from datetime import date
        from decimal import Decimal
        from apps.payroll.models import PayrollProfile

        PayrollProfile.objects.create(
            company=self.company,
            user=self.dev,
            effective_from=date(2026, 1, 1),
            monthly_salary=Decimal("42000.00"),
            is_on_payroll=True,
        )
        response = self.get()
        self.assertTrue(response.context["payroll"]["has_profile"])
        self.assertFalse(response.context["payroll"]["on_payroll"])
        self.assertContains(response, "no payslip has been generated")

    def test_my_tickets_respect_product_access(self):
        """A ticket in a product the developer cannot see must not surface,
        even when they are assigned to it."""
        ProductAccess.objects.create(
            product=self.product, user=self.dev, company=self.company
        )
        hidden = Product.objects.create(name="Hidden", slug="hidden", company=self.company)
        mine = Ticket.objects.create(
            company=self.company, product=self.product, title="Mine",
            status="open", created_by=self.dev,
        )
        mine.assignees.add(self.dev)
        secret = Ticket.objects.create(
            company=self.company, product=hidden, title="Secret",
            status="open", created_by=self.dev,
        )
        secret.assignees.add(self.dev)

        data = get_personal_dashboard_data(self.dev, self.company)
        titles = [t.title for t in data["my_tickets"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Secret", titles)
        self.assertEqual(data["my_ticket_count"], 1)

    def test_tickets_do_not_leak_across_companies(self):
        elsewhere = Ticket.objects.create(
            company=self.other, product=None, title="Theirs",
            status="open", created_by=self.admin,
        )
        elsewhere.assignees.add(self.dev)

        data = get_personal_dashboard_data(self.dev, self.company)
        self.assertEqual([t.title for t in data["my_tickets"]], [])
        self.assertEqual(data["my_ticket_count"], 0)

    def test_dsr_hours_cover_only_this_week_and_only_mine(self):
        from datetime import timedelta
        from decimal import Decimal
        from apps.dsr.models import DSREntry

        today = timezone.localdate()
        DSREntry.objects.create(
            company=self.company, user=self.dev, date=today,
            task_name="Mine today", hours_spent=Decimal("2.5"),
        )
        mate = User.objects.create_user("mate", "mate@test.com", "pass1234")
        Membership.objects.create(user=mate, company=self.company, role="developer")
        DSREntry.objects.create(
            company=self.company, user=mate, date=today,
            task_name="Theirs", hours_spent=Decimal("8.00"),
        )
        # Old entry, same person, outside this week.
        DSREntry.objects.create(
            company=self.company, user=self.dev, date=today - timedelta(days=14),
            task_name="Last sprint", hours_spent=Decimal("7.00"),
        )

        data = get_personal_dashboard_data(self.dev, self.company)
        self.assertEqual(data["dsr"]["dsr_hours"], Decimal("2.5"))
        self.assertEqual(data["dsr"]["dsr_entries"], 1)
        self.assertNotIn(
            "Theirs", [e.task_name for e in data["dsr"]["dsr_recent"]]
        )

    def test_dsr_empty_state_explains_itself(self):
        self.assertContains(self.get(), "Nothing logged this week")

    def test_htmx_request_returns_the_partial(self):
        response = self.get(reverse("dashboards:index"))
        response = self.client.get(
            reverse("dashboards:index"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<html", response.content.decode())

    def test_anonymous_is_redirected_to_login(self):
        self.client.logout()
        response = self.get()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class UnreadableDecimalTakesDownTheDashboardTest(TestCase):
    """The production 500 behind `InvalidOperation at /dashboards/`.

    A single DecimalField cell that SQLite's converter cannot read fails while
    the cursor is being built, so the page dies before any of DashboardView's own
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
            company=self.company,
            user=self.user,
            monthly_salary=self.decimal("50000.00"),
            is_on_payroll=True,
        )

    def test_the_home_page_raises_on_one_unreadable_salary(self):
        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?",
                [float("inf"), self.profile.pk],
            )
        with self.assertRaises(Exception) as ctx:
            self.client.get(reverse("dashboards:index"))
        self.assertEqual(type(ctx.exception).__name__, "InvalidOperation")

    def test_audit_decimals_repair_restores_the_home_page(self):
        from io import StringIO

        from django.core.management import call_command

        with self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?",
                [float("inf"), self.profile.pk],
            )
        buffer = StringIO()
        call_command("audit_decimals", "--fix", "--set", "0.00", stdout=buffer)
        self.assertIn("Repaired 1 cell", buffer.getvalue())
        self.assertEqual(self.client.get(reverse("dashboards:index")).status_code, 200)

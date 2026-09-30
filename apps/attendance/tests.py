from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.attendance import service
from apps.attendance.models import AttendanceRecord, month_bounds, punch
from apps.dashboards.models import ActivityLog

User = get_user_model()


def make_user(username, company, role):
    user = User.objects.create_user(username, f"{username}@test.local", "pass1234")
    from apps.accounts.models import Membership

    Membership.objects.create(user=user, company=company, role=role)
    return user


class AttendanceTestBase(TestCase):
    def setUp(self):
        from apps.accounts.models import Company

        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other_company = Company.objects.create(name="Other", slug="other")

        self.owner = make_user("owner", self.company, "owner")
        self.dev = make_user("dev", self.company, "developer")
        self.viewer = make_user("viewer", self.company, "viewer")
        self.outsider = make_user("outsider", self.other_company, "owner")

        self.client = Client()


class PunchToggleTest(AttendanceTestBase):
    def test_first_punch_creates_record_with_check_in_only(self):
        record, action = punch(self.company, self.dev)

        self.assertEqual(action, "checked_in")
        self.assertIsNotNone(record.check_in)
        self.assertIsNone(record.check_out)
        self.assertTrue(record.is_open)
        self.assertEqual(record.date, timezone.localdate())

    def test_second_punch_closes_the_day(self):
        punch(self.company, self.dev, moment=timezone.now() - timedelta(hours=4))
        record, action = punch(self.company, self.dev, moment=timezone.now())

        self.assertEqual(action, "checked_out")
        self.assertIsNotNone(record.check_out)
        self.assertTrue(record.is_complete)
        self.assertEqual(record.worked_minutes, 240)

    def test_third_punch_same_day_is_a_noop(self):
        punch(self.company, self.dev)
        punch(self.company, self.dev)
        record, action = punch(self.company, self.dev)

        self.assertEqual(action, "unchanged")
        self.assertEqual(AttendanceRecord.objects.filter(company=self.company, user=self.dev).count(), 1)

    def test_check_out_never_precedes_check_in(self):
        now = timezone.now()
        record, action = punch(
            self.company, self.dev, moment=now, notes=""
        )
        # Simulate a clock skew: punching out with an earlier timestamp.
        record.check_out = record.check_in - timedelta(hours=1)
        record.save()
        self.assertEqual(record.worked_minutes, 0)


class PunchClampTest(AttendanceTestBase):
    def test_punch_clamps_checkout_to_checkin(self):
        now = timezone.now()
        record, _ = punch(self.company, self.dev, moment=now)
        record.check_out = now - timedelta(minutes=30)
        record.save()
        record.refresh_from_db()
        # worked_minutes floors at zero rather than going negative.
        self.assertEqual(record.worked_minutes, 0)


class DurationTest(AttendanceTestBase):
    def test_worked_minutes_and_hours(self):
        now = timezone.now()
        record, _ = punch(self.company, self.dev, moment=now - timedelta(hours=7, minutes=30))
        record.check_out = now
        record.save()

        self.assertEqual(record.worked_minutes, 450)
        self.assertEqual(record.worked_hours, Decimal("7.50"))
        self.assertEqual(record.worked_formatted, "7h 30m")

    def test_open_record_has_zero_worked_minutes(self):
        record, _ = punch(self.company, self.dev)
        self.assertEqual(record.worked_minutes, 0)
        self.assertEqual(record.worked_hours, Decimal("0.00"))

    def test_no_record_at_all(self):
        record = AttendanceRecord(company=self.company, user=self.dev)
        self.assertFalse(record.is_open)
        self.assertFalse(record.is_complete)
        self.assertEqual(record.worked_minutes, 0)
        self.assertEqual(record.elapsed_formatted, "N/A")


class OnePunchPerDayTest(AttendanceTestBase):
    def test_unique_constraint_blocks_duplicate_day(self):
        from django.db import IntegrityError, transaction

        now = timezone.now()
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=now.date(), check_in=now
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttendanceRecord.objects.create(
                    company=self.company, user=self.dev, date=now.date(), check_in=now
                )

    def test_same_user_different_day_allowed(self):
        now = timezone.now()
        punch(self.company, self.dev, moment=now - timedelta(days=1))
        punch(self.company, self.dev, moment=now)
        self.assertEqual(AttendanceRecord.objects.filter(user=self.dev).count(), 2)

    def test_same_day_different_company_allowed(self):
        now = timezone.now()
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=now.date(), check_in=now
        )
        AttendanceRecord.objects.create(
            company=self.other_company, user=self.outsider, date=now.date(), check_in=now
        )
        self.assertEqual(AttendanceRecord.objects.filter(date=now.date()).count(), 2)


class PunchViewTest(AttendanceTestBase):
    def test_requires_login(self):
        response = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_check_in_then_out_via_view(self):
        self.client.login(username="dev", password="pass1234")

        response = self.client.post(reverse("attendance:punch"))
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.get(user=self.dev)
        self.assertTrue(record.is_open)

        self.client.post(reverse("attendance:punch"))
        record.refresh_from_db()
        self.assertTrue(record.is_complete)

    def test_punch_logs_activity(self):
        self.client.login(username="dev", password="pass1234")
        self.client.post(reverse("attendance:punch"))
        self.client.post(reverse("attendance:punch"))

        events = set(
            ActivityLog.objects.filter(company=self.company)
            .values_list("event_type", flat=True)
        )
        self.assertIn("attendance_checked_in", events)
        self.assertIn("attendance_checked_out", events)

    def test_third_punch_does_not_double_log(self):
        self.client.login(username="dev", password="pass1234")
        for _ in range(3):
            self.client.post(reverse("attendance:punch"))

        count = ActivityLog.objects.filter(
            company=self.company, event_type="attendance_checked_in"
        ).count()
        self.assertEqual(count, 1)

    def test_htmx_punch_returns_partial(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.post(
            reverse("attendance:punch"), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("punch-control", response.content.decode())

    def test_punch_writes_to_the_request_company_not_another(self):
        self.client.login(username="outsider", password="pass1234")
        self.client.post(reverse("attendance:punch"))

        record = AttendanceRecord.objects.get(user=self.outsider)
        self.assertEqual(record.company, self.other_company)
        self.assertFalse(AttendanceRecord.objects.filter(user=self.dev).exists())


class SelfServiceAccessTest(AttendanceTestBase):
    def test_member_can_view_own_attendance(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(response.status_code, 200)

    def test_cannot_view_another_employees_attendance_via_user_id(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"),
            {"user_id": self.owner.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_viewer_role_can_punch(self):
        """Any company member counts as an employee, whatever the role."""
        self.client.login(username="viewer", password="pass1234")
        self.client.post(reverse("attendance:punch"))
        self.assertTrue(AttendanceRecord.objects.filter(user=self.viewer).exists())


class PrivilegedScopeTest(AttendanceTestBase):
    """Admins may look at anyone in their own company, and no further."""

    def test_admin_can_view_same_company_employee(self):
        punch(self.company, self.dev)
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        )
        self.assertEqual(response.status_code, 200)
        # Must be the target's rows, not the admin's own.
        self.assertEqual([r.user for r in response.context["records"]], [self.dev])

    def test_admin_cannot_view_employee_of_another_company(self):
        punch(self.other_company, self.outsider)
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.outsider.pk}
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_punch_on_behalf_of_someone_else(self):
        """A user_id on the punch POST must not move anyone else's clock."""
        self.client.login(username="owner", password="pass1234")
        self.client.post(reverse("attendance:punch"), {"user_id": self.dev.pk})

        today = timezone.localdate()
        self.assertTrue(AttendanceRecord.objects.filter(
            user=self.owner, date=today).exists())
        self.assertFalse(AttendanceRecord.objects.filter(
            user=self.dev, date=today).exists())

    def test_admin_timesheet_detail_rejects_other_company(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.outsider.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_viewing_other_hides_punch_button(self):
        """The button renders the target's state but would punch the admin."""
        self.client.login(username="owner", password="pass1234")

        own = self.client.get(reverse("attendance:my_attendance"))
        self.assertIsNone(own.context["focus_user"])
        self.assertContains(own, 'id="punch-control"')

        focused = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        )
        self.assertEqual(focused.context["focus_user"], self.dev)
        self.assertNotContains(focused, 'id="punch-control"')
        # And the page says whose data it is, instead of claiming "My Attendance".
        self.assertContains(focused, "dev")
        self.assertNotContains(focused, "<h1>My Attendance</h1>")

    def test_member_always_sees_own_punch_panel(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        )
        self.assertIsNone(response.context["focus_user"])
        self.assertContains(response, 'id="punch-control"')


class TeamViewAccessTest(AttendanceTestBase):
    def test_owner_can_view_team(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:team_attendance"))
        self.assertEqual(response.status_code, 200)

    def test_developer_cannot_view_team(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("attendance:team_attendance"))
        self.assertEqual(response.status_code, 403)

    def test_timesheet_is_admin_only(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(
            self.client.get(reverse("attendance:timesheet")).status_code, 403
        )
        self.client.login(username="owner", password="pass1234")
        self.assertEqual(
            self.client.get(reverse("attendance:timesheet")).status_code, 200
        )

    def test_team_view_does_not_leak_other_company(self):
        punch(self.other_company, self.outsider)
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:team_attendance"))
        self.assertNotContains(response, self.outsider.username)

    def test_outsider_team_view_shows_only_their_own_company(self):
        """An owner of another company sees their team, never ours."""
        punch(self.other_company, self.outsider)
        self.client.login(username="outsider", password="pass1234")
        response = self.client.get(reverse("attendance:team_attendance"))

        self.assertEqual(response.status_code, 200)
        # request.company resolves from the outsider's own Membership, so the
        # team table must contain them and not Acme's members.
        self.assertContains(response, "outsider")
        self.assertNotContains(response, "dev@")
        names = [row["user"].username for row in response.context["team"]]
        self.assertEqual(names, ["outsider"])

    def test_outsider_timesheet_is_scoped_to_their_company(self):
        punch(self.company, self.dev)
        self.client.login(username="outsider", password="pass1234")
        response = self.client.get(reverse("attendance:timesheet"))
        # Their own company has one member; ours must not leak in.
        self.assertEqual(
            [row["user"].username for row in response.context["rows"]],
            ["outsider"],
        )


class AdminEditTest(AttendanceTestBase):
    def setUp(self):
        super().setUp()
        self.record, _ = punch(self.company, self.dev)
        self.record.check_out = self.record.check_in + timedelta(hours=8)
        self.record.save()

    def test_admin_can_edit_a_record(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {
                "check_in": "2026-01-05T09:00",
                "check_out": "2026-01-05T17:30",
                "notes": "forgot to check out",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.record.refresh_from_db()
        self.assertTrue(self.record.is_edited)
        self.assertEqual(self.record.worked_minutes, 510)
        self.assertEqual(self.record.notes, "forgot to check out")

    def test_edit_rejects_checkout_before_checkin(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {"check_in": "2026-01-05T17:00", "check_out": "2026-01-05T09:00"},
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.worked_minutes, 480)
        self.assertFalse(self.record.is_edited)

    def test_non_admin_cannot_edit(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {"check_in": "2026-01-05T09:00", "check_out": "2026-01-05T10:00"},
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_edit_another_companys_record(self):
        self.client.login(username="outsider", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {"check_in": "2026-01-05T09:00", "check_out": "2026-01-05T10:00"},
        )
        self.assertEqual(response.status_code, 404)

    def test_empty_input_clears_the_punch(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {"check_in": "", "check_out": ""},
        )
        self.record.refresh_from_db()
        self.assertIsNone(self.record.check_in)
        self.assertIsNone(self.record.check_out)

    def test_edit_logs_activity(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {"check_in": "2026-01-05T09:00", "check_out": "2026-01-05T17:00"},
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                company=self.company, event_type="attendance_edited"
            ).exists()
        )


class ReportTest(AttendanceTestBase):
    def test_who_is_in_lists_only_open_records(self):
        open_record, _ = punch(self.company, self.dev)
        punch(self.company, self.viewer)
        punch(self.company, self.viewer)  # closes viewer's day

        on_clock = service.get_who_is_in(self.company)
        self.assertEqual([r["user"] for r in on_clock], [self.dev])
        self.assertFalse(on_clock[0]["is_stale"])

    def test_stale_flag_for_forgotten_checkout(self):
        yesterday = timezone.now() - timedelta(days=1)
        punch(self.company, self.dev, moment=yesterday)

        on_clock = service.get_who_is_in(self.company)
        self.assertTrue(on_clock[0]["is_stale"])

    def test_monthly_rows_totals(self):
        now = timezone.now()
        punch(self.company, self.dev, moment=now - timedelta(days=1))
        record = AttendanceRecord.objects.get(user=self.dev)
        record.check_out = record.check_in + timedelta(hours=6)
        record.save()

        rows = service.get_monthly_rows(self.company, now.year, now.month)
        row = next(r for r in rows if r["user"] == self.dev)
        self.assertEqual(row["present_days"], 1)
        self.assertEqual(row["total_minutes"], 360)
        self.assertEqual(row["total_formatted"], "6h 00m")
        self.assertEqual(row["avg_per_day_formatted"], "6h 00m")

    def test_monthly_rows_exclude_other_months(self):
        now = timezone.now()
        other = now.replace(month=1, day=15) if now.month != 1 else now.replace(month=2, day=15)
        punch(self.company, self.dev, moment=other)

        rows = service.get_monthly_rows(self.company, now.year, now.month)
        # Members are always listed, so assert on the minutes rather than on
        # the row count -- another month's punches must contribute nothing.
        self.assertEqual(
            {r["user"].pk for r in rows},
            {self.owner.pk, self.dev.pk, self.viewer.pk},
        )
        self.assertTrue(all(r["total_minutes"] == 0 for r in rows))

    def test_month_grid_covers_every_day(self):
        now = timezone.now()
        grid = service.get_month_grid(self.company, now.year, now.month, self.dev)
        self.assertEqual(len(grid["days"]), 31 if now.month in (1, 3, 5, 7, 8, 10, 12) else 30)
        self.assertEqual(grid["present_days"], 0)

    def test_month_grid_flags_weekends_and_today(self):
        now = timezone.now()
        grid = service.get_month_grid(self.company, now.year, now.month, self.dev)
        today_cells = [d for d in grid["days"] if d["is_today"]]
        self.assertEqual(len(today_cells), 1)
        self.assertTrue(any(d["is_weekend"] for d in grid["days"]))

    def test_empty_month_lists_members_with_zero(self):
        """Every employee appears even with no punches, so nobody vanishes."""
        now = timezone.now()
        rows = service.get_monthly_rows(self.company, now.year, now.month)
        self.assertEqual(
            {r["user"].pk for r in rows},
            {self.owner.pk, self.dev.pk, self.viewer.pk},
        )
        for row in rows:
            self.assertEqual(row["present_days"], 0)
            self.assertEqual(row["total_minutes"], 0)
            self.assertEqual(row["total_formatted"], "0h 00m")
            self.assertEqual(row["avg_per_day_formatted"], "—")

    def test_member_with_no_punches_does_not_change_other_totals(self):
        punch(self.company, self.dev)
        now = timezone.now()
        rows = service.get_monthly_rows(self.company, now.year, now.month)
        dev = next(r for r in rows if r["user"] == self.dev)
        viewer = next(r for r in rows if r["user"] == self.viewer)
        self.assertEqual(dev["present_days"], 1)
        self.assertEqual(viewer["present_days"], 0)


class MonthParsingTest(AttendanceTestBase):
    def test_valid_month_parses(self):
        self.assertEqual(service.parse_month("2026-03"), (2026, 3))

    def test_invalid_month_falls_back_to_today(self):
        today = timezone.localdate()
        for raw in ("garbage", "2026-13", "2026-00", "", None, "2026-1-5-x"):
            self.assertEqual(service.parse_month(raw), (today.year, today.month), raw)

    def test_month_shift_crosses_year_boundary(self):
        self.assertEqual(service.month_shift(2026, 1, -1), (2025, 12))
        self.assertEqual(service.month_shift(2026, 12, 1), (2027, 1))

    def test_month_bounds_are_inclusive(self):
        first, last = service.month_bounds(2026, 2)
        self.assertEqual(first.day, 1)
        self.assertEqual(last.day, 28)

    def test_month_bounds_december(self):
        first, last = service.month_bounds(2026, 12)
        self.assertEqual(first.month, 12)
        self.assertEqual(last.month, 12)
        self.assertEqual(last.day, 31)


class TimesheetViewTest(AttendanceTestBase):
    def test_timesheet_accepts_month_param(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:timesheet"), {"month": "2026-03"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["month_label"], "March 2026")

    def test_timesheet_detail_is_scoped_to_the_company(self):
        self.client.login(username="outsider", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.dev.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_timesheet_detail_for_member(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.dev.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total")


class MonthFilterTest(AttendanceTestBase):
    """The month arrows must scope the table, not just relabel it."""

    def _dates_in(self, month):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"), {"month": month}
        )
        self.assertEqual(response.status_code, 200)
        return {r.date for r in response.context["records"]}

    def _seed_day(self, day):
        check_in = timezone.make_aware(datetime(day.year, day.month, day.day, 9))
        return AttendanceRecord.objects.create(
            company=self.company,
            user=self.owner,
            date=day,
            check_in=check_in,
            check_out=check_in + timedelta(hours=8),
        )

    def test_arrows_change_the_rows_not_just_the_label(self):
        sept = date(2026, 9, 15)
        aug = date(2026, 8, 15)
        self._seed_day(sept)
        self._seed_day(aug)

        self.assertEqual(self._dates_in("2026-09"), {sept})
        self.assertEqual(self._dates_in("2026-08"), {aug})

    def test_month_with_no_records_is_empty(self):
        self._seed_day(date(2026, 9, 15))
        self.assertEqual(self._dates_in("2026-10"), set())

    def test_default_view_shows_only_the_current_month(self):
        today = timezone.localdate().replace(day=15)
        self._seed_day(today)
        # A day from a month ago must not leak into the unfiltered default view.
        self._seed_day(date(2025, 3, 15))

        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(
            {r.date for r in response.context["records"]},
            {today},
        )

    def test_this_month_button_returns_to_the_present(self):
        """Guards against being stranded on a future month with no way back."""
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:my_attendance"), {"month": "2027-01"}
        )
        self.assertEqual(response.status_code, 200)

        link = re.findall(
            r'(<a href="([^"]*)"[^>]*>This month</a>)', response.content.decode()
        )
        self.assertEqual(len(link), 1, "expected exactly one This month link")
        self.assertEqual(link[0][1], reverse("attendance:my_attendance"))
        # Highlighted only while actually viewing the present.
        self.assertNotIn("btn-primary", link[0][0])
        self.assertIn(
            "btn-primary",
            self.client.get(
                reverse("attendance:my_attendance"),
                {"month": timezone.localdate().strftime("%Y-%m")},
            ).content.decode(),
        )

    def test_this_month_button_keeps_the_target_employee(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.dev.pk]),
            {"month": "2027-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("attendance:timesheet_detail", args=[self.dev.pk])}"',
        )

    def test_no_duplicate_or_noop_this_month_links(self):
        """A 'This month' link to ?month=<viewed month> is a no-op dead end.

        Exactly one such link per page, and it must not point at the month
        currently being viewed.
        """
        self.client.login(username="owner", password="pass1234")
        urls = [
            reverse("attendance:my_attendance"),
            reverse("attendance:timesheet"),
            reverse("attendance:timesheet_detail", args=[self.dev.pk]),
        ]
        pattern = r'<a href="([^"]*)"[^>]*>This month</a>'

        for url in urls:
            response = self.client.get(url, {"month": "2027-01"})
            self.assertEqual(response.status_code, 200)
            found = re.findall(pattern, response.content.decode())
            self.assertEqual(
                len(found), 1, f"{url} rendered {len(found)} 'This month' links"
            )
            self.assertNotIn(
                "month=2027-01", found[0], f"{url}: 'This month' is a no-op"
            )


class LeaveShowsInAttendanceTest(AttendanceTestBase):
    """Approved leave must read as leave, not as an absence."""

    def setUp(self):
        super().setUp()
        from apps.leave.models import LeavePolicy, LeaveRequest

        self.policy = LeavePolicy.objects.create(
            company=self.company,
            name="Casual",
            max_days_per_year=Decimal("12.0"),
            max_consecutive_days=Decimal("5.0"),
        )
        self.foreign_policy = LeavePolicy.objects.create(
            company=self.other_company, name="Casual", max_days_per_year=Decimal("12.0")
        )

    def grant(self, user, start, end, status="approved", days=Decimal("3.0"), policy=None):
        from apps.leave.models import LeaveRequest

        return LeaveRequest.objects.create(
            company=self.company,
            user=user,
            policy=policy or self.policy,
            start_date=start,
            end_date=end,
            days=days,
            status=status,
        )

    def test_team_today_flags_on_leave(self):
        today = timezone.localdate()
        self.grant(self.dev, today, today, days=Decimal("1.0"))
        rows = {r["user"].pk: r for r in service.get_team_today(self.company)}
        self.assertTrue(rows[self.dev.pk]["on_leave"])
        self.assertFalse(rows[self.owner.pk]["on_leave"])

    def test_pending_leave_is_not_on_leave(self):
        today = timezone.localdate()
        self.grant(self.dev, today, today, status="pending", days=Decimal("1.0"))
        rows = {r["user"].pk: r for r in service.get_team_today(self.company)}
        self.assertFalse(rows[self.dev.pk]["on_leave"])

    def test_team_view_counts_leave_separately(self):
        today = timezone.localdate()
        self.grant(self.dev, today, today, days=Decimal("1.0"))
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:team_attendance"))
        self.assertEqual(response.context["leave_count"], 1)
        # The employee on leave must not also be counted as absent.
        self.assertEqual(response.context["absent_count"], 2)
        self.assertContains(response, "On leave")

    def test_timesheet_counts_leave_days(self):
        first, _ = month_bounds(timezone.localdate().year, timezone.localdate().month)
        self.grant(self.dev, first, first + timedelta(days=1), days=Decimal("2.0"))
        rows = {r["user"].pk: r for r in service.get_monthly_rows(
            self.company, first.year, first.month
        )}
        self.assertEqual(rows[self.dev.pk]["leave_day_count"], 2)
        self.assertEqual(rows[self.owner.pk]["leave_day_count"], 0)

    def test_month_grid_marks_leave_and_excludes_from_absent(self):
        today = timezone.localdate()
        self.grant(self.dev, today, today, days=Decimal("1.0"))
        grid = service.get_month_grid(self.company, today.year, today.month, self.dev)
        day = next(d for d in grid["days"] if d["date"] == today)
        self.assertTrue(day["on_leave"])
        self.assertEqual(grid["leave_days"], 1)

    def test_leave_day_shows_in_grid_html(self):
        today = timezone.localdate()
        self.grant(self.dev, today, today, days=Decimal("1.0"))
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.dev.pk])
            + f"?month={today.year}-{today.month:02d}"
        )
        self.assertContains(response, "att-leave")

    def test_leave_from_another_company_is_ignored(self):
        from apps.leave.models import LeaveRequest

        today = timezone.localdate()
        LeaveRequest.objects.create(
            company=self.other_company,
            user=self.outsider,
            policy=self.foreign_policy,
            start_date=today,
            end_date=today,
            days=Decimal("1.0"),
            status="approved",
        )
        rows = {r["user"].pk: r for r in service.get_team_today(self.company)}
        self.assertFalse(any(r["on_leave"] for r in rows.values()))

    def test_leave_map_clips_to_requested_range(self):
        from apps.leave.service import approved_leave_map

        first, _ = month_bounds(2026, 3)
        self.grant(self.dev, date(2026, 1, 1), date(2026, 12, 31), days=Decimal("260.0"))
        leave_map = approved_leave_map(self.company, first, date(2026, 3, 31))
        self.assertEqual(leave_map[self.dev.pk], set(
            date(2026, 3, d) for d in range(1, 32)
        ))


class LatePenaltyTest(AttendanceTestBase):
    """The office rule: 10:00 start, 15 min grace, Rs 50 / Rs 100, half day after
    an hour. Bands are stored as minutes-after-start on `WorkShift`, not as
    clock times, so each boundary is a single number to test."""

    def punch_at(self, at, day=None):
        day = day or timezone.localdate()
        return AttendanceRecord.objects.create(
            company=self.company,
            user=self.dev,
            date=day,
            check_in=timezone.make_aware(datetime.combine(day, at)),
            check_out=timezone.make_aware(
                datetime.combine(day, datetime.strptime("19:00", "%H:%M").time())
            ),
        )

    def test_the_default_shift_is_the_office_hours(self):
        shift = service.shift_for(self.company)
        self.assertEqual(shift.start_time, time(10, 0))
        self.assertEqual(shift.end_time, time(19, 0))
        self.assertEqual(shift.break_minutes, 60)
        # 9 hours less a 60 minute break.
        self.assertEqual(shift.worked_minutes_per_day, 480)

    def test_a_company_with_no_shift_row_still_gets_one(self):
        from apps.attendance.models import WorkShift

        self.assertFalse(WorkShift.objects.filter(company=self.company).exists())
        self.assertEqual(service.shift_for(self.company).start_time, time(10, 0))

    def test_the_band_boundaries(self):
        shift = service.shift_for(self.company)
        cases = [
            (0, "on_time"),
            (10, "on_time"),
            (15, "on_time"),   # 10:15 is still on time
            (16, "minor"),     # 10:16 is late enough to cost Rs 50
            (30, "minor"),     # 10:30 is the top of the minor band
            (31, "major"),
            (60, "major"),     # 11:00 is still Rs 100
            (61, "half_day"),  # 11:01 costs half a day
        ]
        for minutes, expected in cases:
            with self.subTest(late=minutes):
                self.assertEqual(shift.band_for_late_minutes(minutes), expected)

    def test_early_arrival_is_not_late(self):
        record = self.punch_at(time(8, 15))
        self.assertEqual(service.lateness_for(record), 0)
        self.assertIsNone(service.late_penalty_for(record))

    def test_a_minor_arrival_costs_fifty_with_a_reason(self):
        penalty = service.late_penalty_for(self.punch_at(time(10, 20)))
        self.assertEqual(penalty["band"], "minor")
        self.assertEqual(Decimal(penalty["amount"]), Decimal("50.00"))
        self.assertEqual(penalty["late_minutes"], 20)
        self.assertIn("10:20", penalty["reason"])
        # The date is part of the reason, not only a sibling field.
        self.assertIn(penalty["date"], penalty["reason"])

    def test_a_major_arrival_costs_a_hundred(self):
        penalty = service.late_penalty_for(self.punch_at(time(10, 45)))
        self.assertEqual(penalty["band"], "major")
        self.assertEqual(Decimal(penalty["amount"]), Decimal("100.00"))

    def test_more_than_an_hour_late_is_a_half_day(self):
        penalty = service.late_penalty_for(self.punch_at(time(11, 30)))
        self.assertEqual(penalty["band"], "half_day")
        # Priced in payroll, not here, so the amount is zero by design.
        self.assertEqual(Decimal(penalty["amount"]), Decimal("0"))
        self.assertIn("half day", penalty["reason"])

    def test_no_punch_is_not_lateness(self):
        """A missing arrival has no time to be late with; guessing costs money."""
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=timezone.localdate()
        )
        self.assertEqual(service.lateness_for(record), 0)
        self.assertIsNone(service.late_penalty_for(record))

    def test_penalties_in_a_period_are_ordered_and_scoped(self):
        from datetime import date as _date

        self.punch_at(time(10, 45), _date(2026, 3, 2))
        self.punch_at(time(10, 20), _date(2026, 3, 3))
        self.punch_at(time(10, 0), _date(2026, 3, 4))  # on time
        self.punch_at(time(11, 30), _date(2026, 3, 9))  # outside the window
        found = service.late_penalties_in_period(
            self.company, self.dev, _date(2026, 3, 1), _date(2026, 3, 5)
        )
        self.assertEqual([f["date"] for f in found], ["2026-03-02", "2026-03-03"])
        self.assertEqual(
            [f["band"] for f in found], ["major", "minor"]
        )

    def test_another_person_and_another_company_are_never_counted(self):
        from apps.attendance.models import WorkShift

        self.punch_at(time(10, 45))
        WorkShift.objects.create(company=self.other_company)  # must not leak
        self.assertEqual(
            service.late_penalties_in_period(
                self.other_company, self.dev, timezone.localdate(),
                timezone.localdate(),
            ),
            [],
        )
        self.assertEqual(
            service.late_penalties_in_period(
                self.company, self.owner, timezone.localdate(),
                timezone.localdate(),
            ),
            [],
        )

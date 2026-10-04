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
        punch(self.company, self.dev, moment=timezone.now() - timedelta(minutes=3))
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

        # Age the check-in past the double-tap guard, as a real day would.
        AttendanceRecord.objects.filter(pk=record.pk).update(
            check_in=record.check_in - timedelta(minutes=5)
        )
        self.client.post(reverse("attendance:punch"))
        record.refresh_from_db()
        self.assertTrue(record.is_complete)

    def test_punch_logs_activity(self):
        self.client.login(username="dev", password="pass1234")
        self.client.post(reverse("attendance:punch"))
        AttendanceRecord.objects.update(check_in=timezone.now() - timedelta(minutes=5))
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

    def punch_control_of(self, response):
        body = response.content.decode()
        start = body.index('id="punch-control"')
        end = body.find('class="att-stats"', start)
        return body[start:end]

    def test_admin_viewing_other_hides_punch_button(self):
        """The button renders the target's state but would punch the admin.

        The panel itself is deliberately still rendered, read-only: hiding the
        whole thing also hid the forgotten-check-out warning, which is the very
        reason an admin opens somebody else's attendance page.
        """
        from apps.attendance.models import AttendanceRecord

        day = timezone.localdate() - timedelta(days=2)
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
            check_in=timezone.make_aware(
                datetime.combine(day, time(10, 0)), timezone.get_current_timezone()
            ),
        )
        self.client.login(username="owner", password="pass1234")

        own = self.client.get(reverse("attendance:my_attendance"))
        self.assertIsNone(own.context["focus_user"])
        self.assertTrue(own.context["can_punch"])
        self.assertContains(own, "<button")

        focused = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        )
        self.assertEqual(focused.context["focus_user"], self.dev)
        control = self.punch_control_of(focused)
        self.assertNotIn("<button", control)
        self.assertNotIn("hx-post", control)
        self.assertIn("no check-out", control)
        # And the page says whose data it is, instead of claiming "My Attendance".
        self.assertContains(focused, "dev")
        self.assertNotContains(focused, "<h1>My Attendance</h1>")

    def test_the_read_only_panel_reports_the_colleagues_days_not_the_admins(self):
        """`record.user` is None on a day the colleague has not punched, so the
        panel used to fall back to the *admin* and warn about the wrong person."""
        from apps.attendance.models import AttendanceRecord

        mine = timezone.localdate() - timedelta(days=4)
        theirs = timezone.localdate() - timedelta(days=2)
        for day, who in ((mine, self.viewer), (theirs, self.dev)):
            AttendanceRecord.objects.create(
                company=self.company, user=who, date=day,
                check_in=timezone.make_aware(
                    datetime.combine(day, time(10, 0)),
                    timezone.get_current_timezone(),
                ),
            )
        self.client.login(username="owner", password="pass1234")
        control = self.punch_control_of(
            self.client.get(
                reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
            )
        )
        self.assertIn(f"{theirs:%b} {theirs.day}", control)
        self.assertNotIn(f"{mine:%b} {mine.day}", control)

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
        # A finished day in the past. An edit may not put a punch in the future,
        # so a record dated today would make these tests depend on the hour.
        day = timezone.localdate() - timedelta(days=2)
        check_in = timezone.make_aware(datetime.combine(day, time(10, 0)))
        self.record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
            check_in=check_in, check_out=check_in + timedelta(hours=8),
        )

    def test_admin_can_edit_a_record(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[self.record.pk]),
            {
                "check_in": f"{self.record.date:%Y-%m-%d}T09:00",
                "check_out": f"{self.record.date:%Y-%m-%d}T17:30",
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
            {"check_in": f"{self.record.date:%Y-%m-%d}T09:00", "check_out": f"{self.record.date:%Y-%m-%d}T17:00"},
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                company=self.company, event_type="attendance_edited"
            ).exists()
        )


class ReportTest(AttendanceTestBase):
    def test_who_is_in_lists_only_open_records(self):
        open_record, _ = punch(self.company, self.dev)
        punch(self.company, self.viewer, moment=timezone.now() - timedelta(minutes=3))
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


class MissingCheckoutTest(AttendanceTestBase):
    """A punch with no check-out must be visibly different from a live one.

    `is_open` is true both for somebody working right now and for a punch
    somebody forgot to close weeks ago. Both used to render as "On clock" with
    a counter that kept ticking, so the second one was invisible.
    """

    def open_record(self, days_ago=0, check_in_hour=10):
        day = timezone.localdate() - timedelta(days=days_ago)
        check_in = timezone.make_aware(
            datetime.combine(day, time(check_in_hour, 0)),
            timezone.get_current_timezone(),
        )
        return AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day, check_in=check_in,
        )

    def month_of(self, record):
        """The ?month= that shows `record`.

        The month views are month-scoped, and a punch a few days back can easily
        fall in the previous month -- on the 2nd of one, "2 days ago" is a
        September punch and October's grid is empty. Every assertion below has
        to ask for the right month rather than assume the current one.
        """
        return f"{record.date:%Y-%m}"

    # --- the three states are distinguishable ---

    def test_an_open_day_today_is_on_the_clock(self):
        record = self.open_record(days_ago=0)
        self.assertTrue(record.is_open)
        self.assertTrue(record.is_open_today)
        self.assertFalse(record.is_stale)
        self.assertEqual(record.missing_checkout_label, "today")

    def test_an_open_day_from_a_previous_day_is_stale_not_on_the_clock(self):
        record = self.open_record(days_ago=3)
        self.assertTrue(record.is_open)
        self.assertFalse(record.is_open_today)
        self.assertTrue(record.is_stale)
        self.assertEqual(record.missing_checkout_label, "3d")

    def test_a_closed_day_is_neither(self):
        day = timezone.localdate() - timedelta(days=2)
        at = timezone.make_aware(
            datetime.combine(day, time(10, 0)), timezone.get_current_timezone()
        )
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day, check_in=at, check_out=at,
        )
        self.assertFalse(record.is_open)
        self.assertFalse(record.is_open_today)
        self.assertFalse(record.is_stale)
        self.assertEqual(record.open_days, 0)

    def test_the_service_reads_staleness_off_the_record(self):
        """`get_who_is_in` computed `is_stale` privately, so nothing else could.

        Two definitions of the same fact is how the other four screens ended up
        unable to tell the cases apart.
        """
        self.open_record(days_ago=5)
        today = self.open_record(days_ago=0)
        rows = {r["record"].pk: r for r in service.get_who_is_in(self.company)}
        self.assertTrue(rows[list(rows)[0]]["is_stale"])
        self.assertFalse(rows[today.pk]["is_stale"])

    # --- an unclosed day counts for the hours it demonstrably worked ---

    def test_the_raw_span_stays_zero_because_the_punches_say_nothing(self):
        record = self.open_record(days_ago=2)
        self.assertEqual(record.worked_minutes, 0)

    def test_an_unclosed_day_counts_its_elapsed_time(self):
        record = self.open_record(days_ago=0)
        record.check_in = timezone.now() - timedelta(minutes=300)
        record.save()
        shift = service.shift_for(self.company)
        self.assertEqual(service.effective_span_for(record, shift), 300)
        self.assertEqual(service.net_minutes_for(record, shift), 300)

    def test_a_long_open_day_is_capped_at_one_working_day(self):
        """Without the cap a forgotten punch accrues hours forever.

        A record left open since October would otherwise report its full elapsed
        span -- hundreds of hours -- inside a single month.
        """
        record = self.open_record(days_ago=30)
        shift = service.shift_for(self.company)
        day = shift.worked_minutes_per_day
        record.check_in = timezone.now() - timedelta(days=30)
        record.save()
        self.assertEqual(service.effective_span_for(record, shift), day)
        # The cap is already net of the break, so it is not deducted twice.
        self.assertEqual(service.net_minutes_for(record, shift), day)

    def test_a_closed_day_is_unaffected_by_the_cap(self):
        day = timezone.localdate() - timedelta(days=1)
        at = timezone.make_aware(
            datetime.combine(day, time(10, 0)), timezone.get_current_timezone()
        )
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
            check_in=at, check_out=at + timedelta(hours=9),
        )
        shift = service.shift_for(self.company)
        self.assertEqual(service.effective_span_for(record, shift), 540)
        self.assertEqual(service.net_minutes_for(record, shift), 480)

    def test_no_check_in_means_no_hours_at_all(self):
        day = timezone.localdate() - timedelta(days=1)
        record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
        )
        shift = service.shift_for(self.company)
        self.assertEqual(service.effective_span_for(record, shift), 0)
        self.assertEqual(service.net_minutes_for(record, shift), 0)

    def test_an_unclosed_day_does_not_create_a_late_penalty(self):
        """The cap changes reporting only. Payroll reads `check_in` alone."""
        day = timezone.localdate() - timedelta(days=1)
        late = timezone.make_aware(
            datetime.combine(day, time(10, 50)), timezone.get_current_timezone()
        )
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day, check_in=late,
        )
        penalties = service.late_penalties_in_period(
            self.company, self.dev, day, day,
        )
        self.assertEqual(len(penalties), 1)
        self.assertEqual(penalties[0]["band"], "major")

    # --- and it is visible, and fixable, on every screen that shows a day ---

    def my_page(self, **params):
        self.client.login(username="dev", password="pass1234")
        url = reverse("attendance:my_attendance")
        return self.client.get(url, params)

    def team_page(self):
        self.client.login(username="owner", password="pass1234")
        return self.client.get(reverse("attendance:team_attendance"))

    def test_my_own_page_says_it_when_i_forgot_to_check_out(self):
        """The page that started this: no flag at all, just an empty cell."""
        record = self.open_record(days_ago=2)
        body = self.my_page(month=self.month_of(record)).content.decode()
        self.assertIn("not checked out", body)
        self.assertIn("No check-out", body)

    def test_my_own_page_does_not_call_a_live_punch_a_forgotten_one(self):
        record = self.open_record(days_ago=0)
        body = self.my_page(month=self.month_of(record)).content.decode()
        # Today's open punch is legitimately "on clock" -- the flag is the
        # absence of a forgotten-check-out warning, not its presence.
        self.assertNotIn("not checked out", body)
        self.assertIn("on clock", body)

    def test_the_team_page_lists_it_and_offers_the_fix(self):
        self.open_record(days_ago=4)
        body = self.team_page().content.decode()
        self.assertIn("No check-out", body)
        self.assertIn("Set check-out", body)

    def test_the_timesheet_counts_it_per_employee(self):
        stale = self.open_record(days_ago=2)
        self.open_record(days_ago=0)  # today's is legitimately open, not a fault
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(
            reverse("attendance:timesheet"), {"month": self.month_of(stale)}
        )
        body = response.content.decode()
        self.assertIn("No check-out", body)
        rows = response.context["rows"]
        dev_row = next(r for r in rows if r["user"] == self.dev)
        self.assertEqual(dev_row["open_days"], 1)

    def test_the_calendar_grid_flags_the_day_and_links_the_edit(self):
        record = self.open_record(days_ago=1)
        self.client.login(username="owner", password="pass1234")
        body = self.client.get(
            reverse("attendance:timesheet_detail", args=[self.dev.pk]),
            {"month": self.month_of(record)},
        ).content.decode()
        self.assertIn("no out", body)
        self.assertIn(reverse("attendance:attendance_edit", args=[record.pk]), body)

    def test_the_edit_form_is_reachable_as_a_plain_link(self):
        """The grid has no room for an inline form, but it has room for a link."""
        record = self.open_record(days_ago=1)
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("attendance:attendance_edit",
                                           args=[record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No check-out was recorded")
        self.assertContains(response, f'id="edit_check_out_{record.pk}"')

    def test_a_non_admin_cannot_open_the_edit_form(self):
        record = self.open_record(days_ago=1)
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("attendance:attendance_edit",
                                           args=[record.pk]))
        self.assertEqual(response.status_code, 403)

    def test_the_edit_form_is_prefilled_with_the_end_of_the_shift(self):
        """The admin is correcting a forgotten punch, not typing six fields.

        Prefilled with closing time because the whole point of the cap is to
        assume they left then; making the admin retype it defeats that.
        """
        record = self.open_record(days_ago=1)
        shift = service.shift_for(self.company)
        self.client.login(username="owner", password="pass1234")
        body = self.client.get(reverse("attendance:attendance_edit",
                                       args=[record.pk])).content.decode()
        self.assertIn(
            f'value="{record.date:%Y-%m-%d}T{shift.end_time:%H:%M}"', body
        )

    def test_an_admin_can_still_see_the_inline_edit_on_a_colleagues_page(self):
        record = self.open_record(days_ago=2)
        self.client.login(username="owner", password="pass1234")
        body = self.client.get(
            reverse("attendance:my_attendance"),
            {"user_id": self.dev.pk, "month": self.month_of(record)},
        ).content.decode()
        self.assertIn("Set check-out", body)
        self.assertIn(reverse("attendance:attendance_edit", args=[record.pk]), body)

    def test_an_employee_gets_no_edit_button_on_their_own_page(self):
        """The edit form is a payroll mutation, so it is admin-only.

        Rendering it for everyone would mean posting to a URL that 403s.
        """
        record = self.open_record(days_ago=2)
        body = self.my_page(month=self.month_of(record)).content.decode()
        self.assertNotIn("Set check-out", body)
        self.assertNotIn(reverse("attendance:attendance_edit", args=[record.pk]), body)

    # --- setting the check-out resolves every surface at once ---

    def test_setting_the_check_out_clears_the_flag_everywhere(self):
        record = self.open_record(days_ago=2)
        day = record.date
        end = timezone.make_aware(
            datetime.combine(day, time(19, 0)), timezone.get_current_timezone()
        )
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[record.pk]),
            {"check_in": f"{day:%Y-%m-%d}T10:00", "check_out": f"{day:%Y-%m-%d}T19:00"},
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertFalse(record.is_stale)
        self.assertEqual(record.worked_minutes, 540)
        self.assertNotIn(
            "not checked out", self.my_page(month=self.month_of(record)).content.decode()
        )

    def test_clearing_the_check_out_keeps_the_day_open(self):
        """An admin may want it left open; the box can be emptied deliberately."""
        record = self.open_record(days_ago=2)
        day = record.date
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("attendance:attendance_edit", args=[record.pk]),
            {"check_in": f"{day:%Y-%m-%d}T10:00", "check_out": ""},
        )
        record.refresh_from_db()
        self.assertTrue(record.is_stale)
        self.assertIsNone(record.check_out)

    def test_it_returns_to_where_the_admin_started_editing(self):
        record = self.open_record(days_ago=1)
        day = record.date
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[record.pk]),
            {"check_in": f"{day:%Y-%m-%d}T10:00", "check_out": f"{day:%Y-%m-%d}T19:00",
             "next": f"{reverse('attendance:timesheet_detail', args=[self.dev.pk])}?month=2026-01"},
        )
        self.assertRedirects(
            response,
            f"{reverse('attendance:timesheet_detail', args=[self.dev.pk])}?month=2026-01",
        )

    def test_an_off_site_next_is_refused(self):
        """`next` is a redirect target from user input; `//evil.test` is a host."""
        record = self.open_record(days_ago=1)
        day = record.date
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("attendance:attendance_edit", args=[record.pk]),
            {"check_in": f"{day:%Y-%m-%d}T10:00", "check_out": f"{day:%Y-%m-%d}T19:00",
             "next": "//evil.test/pwn"},
        )
        self.assertRedirects(response, reverse("attendance:team_attendance"))


class PunchPanelTest(AttendanceTestBase):
    """The punch control is the page's only job, so its content is a contract."""

    def punch_in(self, at):
        from apps.attendance.models import AttendanceRecord

        today = timezone.localdate()
        return AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=today, check_in=at,
        )

    def panel(self):
        self.client.login(username="dev", password="pass1234")
        return self.client.get(reverse("attendance:my_attendance")).content.decode()

    def panel_markup(self):
        """Just the punch control, without the stylesheet.

        Asserting words like "late" against the whole page matches `.punch-late`
        in the CSS and passes for the wrong reason.
        """
        body = self.panel()
        start = body.index('id="punch-control"')
        # `att-stats` is a class; anchoring on an id that does not exist silently
        # slices to the end of the page and matches words in later markup.
        end = body.find('class="att-stats"', start)
        self.assertNotEqual(end, -1, "punch panel is no longer before the stats")
        return body[start:end]

    def htmx_panel(self):
        self.client.login(username="dev", password="pass1234")
        return self.client.post(
            reverse("attendance:punch"), headers={"HX-Request": "true"}
        ).content.decode()

    def at(self, hour, minute=0, days_ago=0):
        day = timezone.localdate() - timedelta(days=days_ago)
        return timezone.make_aware(
            datetime.combine(day, time(hour, minute)), timezone.get_current_timezone()
        )

    def test_it_says_when_you_checked_in_not_only_how_long(self):
        """The label said "since" and then printed a duration.

        The clock time is the number an employee actually wants, and it was
        nowhere on the panel.
        """
        self.punch_in(self.at(10, 2))
        body = self.panel()
        self.assertIn("On the clock since", body)
        self.assertIn("10:02 AM", body)

    def test_it_shows_the_office_hours(self):
        """Arriving late is priced, so the shift has to be visible at the button."""
        body = self.panel()
        self.assertIn("Shift 10:00–19:00", body)

    def test_it_says_late_the_moment_it_happens(self):
        """Otherwise the first notice of a penalty is a payslip weeks later."""
        self.punch_in(self.at(10, 45))
        body = self.panel()
        self.assertIn("45m late", body)
        self.assertNotIn("on time", body)

    def test_a_half_day_arrival_says_so(self):
        self.punch_in(self.at(11, 20))
        self.assertIn("half day", self.panel())

    def test_arriving_on_time_says_on_time(self):
        self.punch_in(self.at(10, 5))
        body = self.panel()
        self.assertIn("on time", body)
        self.assertNotIn("m late", body)

    def test_it_does_not_invent_lateness_before_you_arrive(self):
        """No punch yet means no arrival time, so there is nothing to be late."""
        body = self.panel_markup()
        self.assertNotIn("late", body)
        self.assertNotIn("on time", body)

    def test_the_lateness_it_shows_is_the_one_the_payslip_charges(self):
        """Same `late_penalty_for` call, so the panel cannot quote a different
        number from the payslip line it is warning about."""
        record = self.punch_in(self.at(10, 45))
        band = service.late_penalty_for(record, service.shift_for(self.company))["band"]
        self.assertEqual(band, "major")
        self.assertIn("45m late", self.panel_markup())

    def test_the_elapsed_counter_is_not_announced_every_thirty_seconds(self):
        """`aria-live` on a counter that refreshes every 30s interrupts forever."""
        self.punch_in(self.at(10, 2))
        body = self.panel_markup()
        self.assertIn('x-text="elapsed"', body)
        self.assertNotIn('aria-live', body)

    def test_the_elapsed_counter_still_shows_a_value_without_javascript(self):
        """Alpine only ticks the counter client-side; the server renders the
        first value, or the box is blank until htmx and Alpine both boot."""
        self.punch_in(self.at(10, 2))
        body = self.panel_markup()
        self.assertRegex(body, r'x-text="elapsed">\d+h \d{2}m<')

    def test_the_punch_result_is_announced(self):
        body = self.htmx_panel()
        self.assertIn('role="status"', body)
        self.assertIn("Checked in at", body)

    def test_a_double_click_cannot_send_a_second_punch(self):
        """The panel re-renders in place, so two rapid clicks both posted.

        `punch` answered the second with its `unchanged` no-op, which replaced
        "Checked in at 10:02 AM." with "already checked in and out" — the
        employee saw the opposite of what happened.
        """
        body = self.panel()
        self.assertIn('hx-disabled-elt="this"', body)

    def test_the_button_still_works_without_javascript(self):
        self.assertIn('method="post"', self.panel())
        self.assertIn(f'action="{reverse("attendance:punch")}"', self.panel())

    def test_both_buttons_exist_and_are_labelled(self):
        """Once "on the clock", so the check-out button is reachable."""
        self.assertIn("Check in", self.panel())
        self.punch_in(self.at(10, 2))
        self.assertIn("Check out", self.panel())

    def test_the_two_buttons_are_visually_distinct(self):
        """`punch-btn-in` / `punch-btn-out` were used but never defined, so both
        buttons rendered as the same plain `.btn`."""
        self.punch_in(self.at(10, 2))
        body = self.panel()
        self.assertIn("punch-btn punch-btn-out", body)
        for selector in (".punch-btn-in{", ".punch-btn-out{"):
            self.assertIn(selector, body)

    def test_the_panel_warns_about_a_forgotten_check_out(self):
        """The complaint that started this: the panel said nothing about it."""
        from apps.attendance.models import AttendanceRecord

        today = timezone.localdate()
        for offset in (1, 5):
            day = today - timedelta(days=offset)
            AttendanceRecord.objects.create(
                company=self.company, user=self.dev, date=day,
                check_in=self.at(10, 0, days_ago=offset),
            )
        body = self.panel()
        self.assertIn("2 earlier days with no check-out", body)
        self.assertIn("capped at one working", body)

    def test_the_warning_lists_the_days_and_is_readable(self):
        from apps.attendance.models import AttendanceRecord

        day = timezone.localdate() - timedelta(days=3)
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
            check_in=self.at(10, 0, days_ago=3),
        )
        body = self.panel()
        self.assertIn(f"{day:%b} {day.day}", body)
        self.assertIn("until an admin closes it out", body)

    def test_no_warning_when_every_day_is_closed(self):
        self.punch_in(self.at(10, 2))
        body = self.panel()
        self.assertNotIn("no check-out", body)

    def test_todays_open_punch_is_not_reported_as_a_forgotten_one(self):
        """Today's record is legitimately open; calling it forgotten would make
        the warning appear on every working day and stop meaning anything."""
        self.punch_in(self.at(10, 2))
        self.assertNotIn("no check-out", self.panel())

    def test_the_warning_spans_every_month_not_the_one_on_screen(self):
        """A punch from last month still costs the days between check-in and
        closing time until it is fixed, so a month filter would hide it."""
        from apps.attendance.models import AttendanceRecord

        old = timezone.localdate() - timedelta(days=60)
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=old,
            check_in=timezone.make_aware(
                datetime.combine(old, time(10, 0)), timezone.get_current_timezone()
            ),
        )
        self.client.login(username="dev", password="pass1234")
        self.assertIn("no check-out", self.panel_markup())

    def test_a_colleagues_forgotten_day_does_not_warn_you(self):
        from apps.attendance.models import AttendanceRecord

        day = timezone.localdate() - timedelta(days=2)
        AttendanceRecord.objects.create(
            company=self.company, user=self.viewer, date=day,
            check_in=self.at(10, 0, days_ago=2),
        )
        self.assertNotIn("no check-out", self.panel())

    def test_an_admin_reading_a_colleague_sees_that_colleagues_warning(self):
        from apps.attendance.models import AttendanceRecord

        day = timezone.localdate() - timedelta(days=2)
        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=day,
            check_in=self.at(10, 0, days_ago=2),
        )
        self.client.login(username="owner", password="pass1234")
        body = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        ).content.decode()
        self.assertIn("no check-out", body)

    def test_the_htmx_re_render_keeps_the_same_information(self):
        """The punch response re-renders the partial, and a panel that loses the
        shift hours or the lateness on the first click is worse than the old one."""
        self.punch_in(self.at(10, 45))
        self.client.login(username="dev", password="pass1234")
        body = self.client.post(
            reverse("attendance:punch"), headers={"HX-Request": "true"}
        ).content.decode()
        # Every state carries the shift and the lateness, so a punch cannot
        # swap one for the other and lose the penalty the employee just incurred.
        for state in ("Checked out", "45m late", "Shift 10:00–19:00"):
            self.assertIn(state, body)
        self.assertNotIn("punch-panel", body)

    def test_a_first_punch_returns_a_complete_panel_not_a_stub(self):
        self.client.login(username="dev", password="pass1234")
        body = self.client.post(
            reverse("attendance:punch"), headers={"HX-Request": "true"}
        ).content.decode()
        self.assertIn("Checked in at", body)
        self.assertIn("Shift 10:00–19:00", body)
        self.assertIn("Check out", body)

    def test_an_admin_reading_a_colleague_is_offered_no_button(self):
        """The button would punch the viewer, not the person on screen."""
        self.client.login(username="owner", password="pass1234")
        body = self.client.get(
            reverse("attendance:my_attendance"), {"user_id": self.dev.pk}
        ).content.decode()
        control = body[body.index('id="punch-control"'):]
        control = control[:control.index('class="att-stats"')]
        self.assertNotIn("<button", control)
        self.assertNotIn('hx-post', control)
        self.assertNotIn("Check in", control)
        self.assertNotIn("Check out", control)

    def test_it_uses_the_shared_icon_set_not_hand_written_svg(self):
        """`{% icon %}` is the project mechanism; this partial still had raw SVG
        bodies, so the punch panel did not share the nav's stroke set."""
        punch = self.panel_markup()
        svgs = re.findall(r"<svg[^>]*>", punch)
        self.assertTrue(svgs, "the punch panel draws no icon at all")
        for svg in svgs:
            self.assertIn('class="ic"', svg)

    def test_there_is_no_dead_punch_panel_wrapper_left(self):
        """`.punch-panel` was `justify-content:space-between` around exactly one
        child, so the flex was doing nothing."""
        self.assertNotIn("punch-panel", self.panel())


class DoubleTapAndConstraintTest(AttendanceTestBase):
    """A double tap closed the day at 0 minutes and blocked checking in again."""

    def test_a_second_tap_right_after_checking_in_is_ignored(self):
        now = timezone.now()
        record, first = punch(self.company, self.dev, moment=now)
        _, second = punch(self.company, self.dev, moment=now + timedelta(seconds=2))
        self.assertEqual((first, second), ("checked_in", "too_soon"))
        record.refresh_from_db()
        self.assertIsNone(record.check_out)

    def test_a_real_check_out_after_the_gap_still_works(self):
        now = timezone.now()
        punch(self.company, self.dev, moment=now - timedelta(minutes=3))
        record, action = punch(self.company, self.dev, moment=now)
        self.assertEqual(action, "checked_out")
        self.assertIsNotNone(record.check_out)

    def test_the_view_tells_the_person_what_happened(self):
        self.client.login(username="dev", password="pass1234")
        self.client.post(reverse("attendance:punch"))
        response = self.client.post(reverse("attendance:punch"), follow=True)
        self.assertContains(response, "Give it a minute")
        from apps.attendance.models import AttendanceRecord

        record = AttendanceRecord.objects.get(company=self.company, user=self.dev)
        self.assertIsNone(record.check_out)

    def test_a_company_cannot_have_two_work_shifts(self):
        from django.db import IntegrityError, transaction

        from apps.attendance.models import WorkShift

        WorkShift.objects.create(company=self.company)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WorkShift.objects.create(company=self.company)

    def test_shift_for_keeps_returning_the_one_row(self):
        first = service.shift_for(self.company)
        self.assertEqual(service.shift_for(self.company).pk, first.pk)


class EditedPunchValidationTest(AttendanceTestBase):
    def setUp(self):
        super().setUp()
        from apps.attendance.models import AttendanceRecord

        self.day = timezone.localdate() - timedelta(days=2)
        self.record = AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=self.day,
            check_in=timezone.make_aware(datetime.combine(self.day, time(10, 0))),
        )
        self.client.login(username="owner", password="pass1234")
        self.url = reverse("attendance:attendance_edit", args=[self.record.pk])

    def post(self, check_in, check_out):
        return self.client.post(self.url, {"check_in": check_in, "check_out": check_out}, follow=True)

    def test_a_punch_on_another_day_is_refused(self):
        other = self.day - timedelta(days=5)
        response = self.post(f"{other:%Y-%m-%d}T10:00", "")
        self.assertContains(response, "has to fall on")
        self.record.refresh_from_db()
        self.assertEqual(timezone.localtime(self.record.check_in).date(), self.day)

    def test_a_future_check_out_is_refused(self):
        future = timezone.localdate() + timedelta(days=3)
        response = self.post(f"{self.day:%Y-%m-%d}T10:00", f"{future:%Y-%m-%d}T19:00")
        self.assertContains(response, "cannot be in the future")

    def test_a_night_shift_may_close_the_next_morning(self):
        next_day = self.day + timedelta(days=1)
        response = self.post(f"{self.day:%Y-%m-%d}T22:00", f"{next_day:%Y-%m-%d}T06:00")
        self.assertContains(response, "Updated")
        self.record.refresh_from_db()
        self.assertIsNotNone(self.record.check_out)


class TeamPageShowsYouTest(AttendanceTestBase):
    """An admin could not find their own row in the team view."""

    def get(self, username="owner"):
        self.client.login(username=username, password="pass1234")
        return self.client.get(reverse("attendance:team_attendance"))

    def test_your_own_row_is_first_and_marked(self):
        response = self.get()
        team = response.context["team"]
        self.assertTrue(team[0]["is_me"])
        self.assertEqual(team[0]["user"], self.owner)
        self.assertContains(response, 'class="you"')
        self.assertContains(response, "Your day")

    def test_your_punch_shows_in_your_day_card(self):
        punch(self.company, self.owner, moment=timezone.now() - timedelta(hours=2))
        response = self.get()
        self.assertEqual(response.context["me"]["state"], "clock")
        self.assertContains(response, "On the clock since")

    def test_every_row_links_to_that_persons_history(self):
        response = self.get()
        self.assertContains(response, f"?user_id={self.dev.pk}")

    def test_each_row_carries_seven_days(self):
        response = self.get()
        self.assertTrue(all(len(row["week"]) == 7 for row in response.context["team"]))

    def test_no_email_addresses_are_shown(self):
        self.assertNotContains(self.get(), "@test.local")


class PunchPanelLiveCounterTest(AttendanceTestBase):
    """The counter's start time used to be pasted in as an unquoted ISO string,
    which is a syntax error in Alpine, so it never ticked."""

    def test_the_start_is_an_integer_not_a_bare_date(self):
        record, _ = punch(self.company, self.dev, moment=timezone.now() - timedelta(hours=1))
        self.client.login(username="dev", password="pass1234")
        body = self.client.get(reverse("attendance:my_attendance")).content.decode()
        expected = int(record.check_in.timestamp() * 1000)
        self.assertIn(f"since: {expected},", body)
        self.assertNotRegex(body, r"since: \d{4}-\d{2}-\d{2}T")

    def test_the_week_strip_is_there(self):
        self.client.login(username="dev", password="pass1234")
        body = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertEqual(body.count('class="week-day'), 7)

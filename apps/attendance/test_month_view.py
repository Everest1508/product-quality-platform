from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance.models import AttendanceRecord

User = get_user_model()


class MonthGlanceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("emp", "e@t.local", "pass1234")
        Membership.objects.create(user=self.user, company=self.company, role="developer")
        self.client.login(username="emp", password="pass1234")

    def day(self, offset):
        return timezone.localdate().replace(day=1) + timedelta(days=offset)

    def punch(self, day, hours):
        start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time().replace(hour=10)))
        return AttendanceRecord.objects.create(
            company=self.company, user=self.user, date=day, check_in=start, check_out=start + timedelta(hours=hours),
        )

    def grant_leave(self, day, status="approved", user=None):
        from apps.leave.models import LeavePolicy, LeaveRequest

        policy, _ = LeavePolicy.objects.get_or_create(
            company=self.company, name="Casual",
            defaults={"max_days_per_year": Decimal("12")},
        )
        return LeaveRequest.objects.create(
            company=self.company, user=user or self.user, policy=policy,
            start_date=day, end_date=day, days=Decimal("1"), status=status,
        )

    def test_approved_leave_is_a_leave_square_not_no_punch(self):
        day = date(2026, 11, 2)  # a Monday in the month from the bug report
        self.grant_leave(day)
        res = self.client.get(reverse("attendance:my_attendance"), {"month": "2026-11"})
        cell = next(c for c in res.context["month_cells"] if c["day"] == day.day)
        self.assertEqual(cell["state"], "leave")
        self.assertIn("leave", cell["title"])
        self.assertEqual(res.context["month_counts"]["leave"], 1)
        self.assertContains(res, "mg mg-leave")
        self.assertContains(res, "Approved leave")

    def test_pending_leave_is_still_a_working_day_with_no_punch(self):
        day = date(2026, 11, 2)
        self.grant_leave(day, status="pending")
        res = self.client.get(reverse("attendance:my_attendance"), {"month": "2026-11"})
        cell = next(c for c in res.context["month_cells"] if c["day"] == day.day)
        self.assertEqual(cell["state"], "none")
        self.assertEqual(res.context["month_counts"]["leave"], 0)

    def test_admin_viewing_a_colleague_sees_that_colleagues_leave(self):
        from apps.accounts.models import Membership

        admin = User.objects.create_user("boss", "b@t.local", "pass1234")
        Membership.objects.create(user=admin, company=self.company, role="admin")
        self.grant_leave(date(2026, 11, 2))                     # the employee
        self.grant_leave(date(2026, 11, 3), user=admin)          # the viewer
        self.client.login(username="boss", password="pass1234")
        res = self.client.get(reverse("attendance:my_attendance"), {
            "user_id": self.user.pk, "month": "2026-11",
        })
        states = {c["day"]: c["state"] for c in res.context["month_cells"]}
        self.assertEqual(states[2], "leave")
        self.assertEqual(states[3], "none")   # the viewer's own leave doesn't leak in
        self.assertEqual(res.context["month_counts"]["leave"], 1)

    def test_the_month_view_summarises_hours_and_days(self):
        first = timezone.localdate().replace(day=1)
        self.punch(first, 9)
        res = self.client.get(reverse("attendance:my_attendance"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context["month_present_days"], 1)
        self.assertIn("h", res.context["month_total_formatted"])
        self.assertContains(res, "month-glance")

    def test_a_full_day_and_a_part_day_are_told_apart(self):
        full, part = self.day(0), self.day(1)
        self.punch(full, 9)
        self.punch(part, 3)
        res = self.client.get(reverse("attendance:my_attendance"), {"month": full.strftime("%Y-%m")})
        states = {c["day"]: c["state"] for c in res.context["month_cells"]}
        self.assertEqual(states[full.day], "full")
        self.assertEqual(states[part.day], "part")
        self.assertEqual(res.context["month_counts"]["full"], 1)
        self.assertEqual(res.context["month_counts"]["part"], 1)

    def test_a_past_weekday_with_no_punch_is_marked(self):
        res = self.client.get(reverse("attendance:my_attendance"), {"month": "2020-03"})
        states = {c["day"]: c["state"] for c in res.context["month_cells"]}
        self.assertEqual(states[2], "none")      # Monday 2 March 2020
        self.assertEqual(states[1], "rest")      # Sunday
        self.assertEqual(res.context["month_leading_blanks"], 6)

    def test_future_days_are_not_called_missing(self):
        nxt = (timezone.localdate().replace(day=1) + timedelta(days=40)).strftime("%Y-%m")
        res = self.client.get(reverse("attendance:my_attendance"), {"month": nxt})
        self.assertTrue(all(c["state"] in ("future", "rest") for c in res.context["month_cells"]))

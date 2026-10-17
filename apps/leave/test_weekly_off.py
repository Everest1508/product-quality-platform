"""Leave is charged on the company's working days, so the weekly offs decide the count."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import service as attendance
from apps.attendance.models import weekly_off_for
from apps.leave import service
from apps.leave.models import LeavePolicy

User = get_user_model()


class LeaveFollowsWeeklyOffTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("ann", password="x")
        Membership.objects.create(user=self.user, company=self.co, role="developer")
        self.policy = LeavePolicy.objects.create(company=self.co, name="Casual", is_paid=True)
        # A Friday a week or so ahead, and the Monday after it.
        friday = timezone.localdate() + timedelta(days=7)
        self.friday = friday + timedelta(days=(4 - friday.weekday()) % 7)
        self.monday = self.friday + timedelta(days=3)

    def set_off(self, *days):
        attendance.set_weekly_off(self.co, [str(d) for d in days])

    def charge(self, start, end):
        return service.validate_request(self.co, self.user, self.policy, start, end, False)

    def test_friday_to_monday_is_two_days_by_default(self):
        self.assertEqual(service.working_days(self.friday, self.monday), 2)
        self.assertEqual(self.charge(self.friday, self.monday), Decimal("2"))

    def test_a_company_that_works_saturdays_is_charged_for_them(self):
        self.set_off(6)
        self.assertEqual(self.charge(self.friday, self.monday), Decimal("3"))

    def test_a_company_with_a_different_weekly_off_is_charged_on_the_other_days(self):
        self.set_off(4, 5)  # Friday and Saturday off; Sunday works
        self.assertEqual(self.charge(self.friday, self.monday), Decimal("2"))  # Sunday and Monday
        with self.assertRaisesMessage(ValidationError, "weekend only"):
            self.charge(self.friday, self.friday + timedelta(days=1))  # Friday and Saturday

    def test_the_apply_screen_preview_counts_the_same_days(self):
        from django.urls import reverse

        self.client.login(username="ann", password="x")
        post = lambda: self.client.post(reverse("leave:split_preview"), {
            "policy_id": self.policy.pk, "start_date": self.friday.isoformat(), "end_date": self.monday.isoformat(),
        })
        self.assertEqual(post().context["days"], 2)
        self.set_off(6)
        self.assertEqual(post().context["days"], 3)

    def test_the_team_calendar_shades_the_weekly_offs(self):
        shaded = lambda: {
            d["date"].day for w in service.month_calendar(self.co, 2026, 10)["weeks"]
            for d in w if d["is_weekend"] and d["in_month"]
        }
        self.assertEqual(shaded(), {3, 4, 10, 11, 17, 18, 24, 25, 31})
        self.set_off(6)
        self.assertEqual(shaded(), {4, 11, 18, 25})

    def test_company_without_a_shift_row_uses_saturday_and_sunday(self):
        self.assertEqual(weekly_off_for(self.co), {5, 6})

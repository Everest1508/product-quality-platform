import re
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.leave import service
from apps.leave.forms import LeaveRequestForm
from apps.core.icons import ICONS, ICON_NAMES, render_icon
from apps.leave.models import LeavePolicy, LeaveRequest


def make_user(username, company, role="developer", approver=False):
    user = get_user_model().objects.create_user(
        username=username, password="pass1234", email=f"{username}@acme.test"
    )
    Membership.objects.create(
        user=user, company=company, role=role, is_leave_approver=approver
    )
    return user


class LeaveTestBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")

        self.owner = make_user("owner", self.company, "owner")
        self.manager = make_user("manager", self.company, "admin")
        self.approver = make_user("approver", self.company, "developer", approver=True)
        self.emp = make_user("emp", self.company)
        self.outsider = make_user("outsider", self.other, "owner")

        self.casual = LeavePolicy.objects.create(
            company=self.company,
            name="Casual",
            max_days_per_year=Decimal("12.0"),
            max_consecutive_days=Decimal("3.0"),
        )
        self.unpaid = LeavePolicy.objects.create(
            company=self.company,
            name="Unpaid",
            max_days_per_year=None,
            max_consecutive_days=None,
            is_paid=False,
        )

        self.client = Client()

    def monday(self, weeks=0):
        """A Monday at least `weeks` ahead of today, so tests never fall in a
        weekend-only range."""
        today = timezone.localdate()
        ahead = today + timedelta(days=7 * (weeks + 1))
        return ahead + timedelta(days=(7 - ahead.weekday()) % 7)

    def first_monday(self, min_days_ahead=14):
        """First Monday at least `min_days_ahead` out."""
        d = timezone.localdate() + timedelta(days=min_days_ahead)
        return d + timedelta(days=(7 - d.weekday()) % 7)

    def make_request(self, user=None, policy=None, start=None, end=None,
                     half=False, days=None, status="pending", paid=None,
                     unpaid=None, split_mode="auto", reason=""):
        start = start or self.monday()
        return LeaveRequest.objects.create(
            company=self.company,
            user=user or self.emp,
            policy=policy or self.casual,
            start_date=start,
            end_date=end or start,
            is_half_day=half,
            days=days if days is not None else Decimal("1.0"),
            status=status,
            paid_days=paid,
            unpaid_days=unpaid,
            split_mode=split_mode,
            reason=reason,
        )


class FormatDaysTest(TestCase):
    def test_it_takes_a_plain_int(self):
        """`working_days` returns an int, and this is the renderer for it.

        It used to call `.normalize()` on whatever arrived, so an int raised
        `AttributeError` from inside a reason string.
        """
        self.assertEqual(service.format_days(5), "5")
        self.assertEqual(service.format_days(0), "0")
        self.assertEqual(service.format_days(10000), "10000")

    def test_never_uses_scientific_notation(self):
        self.assertEqual(service.format_days(Decimal("12.0")), "12")
        self.assertEqual(service.format_days(Decimal("10.0")), "10")
        self.assertEqual(service.format_days(Decimal("11.5")), "11.5")
        self.assertEqual(service.format_days(Decimal("0.5")), "0.5")
        self.assertEqual(service.format_days(None), "—")


class WorkingDaysTest(TestCase):
    def test_counts_monday_to_friday(self):
        monday = date(2026, 9, 7)
        friday = date(2026, 9, 11)
        self.assertEqual(service.working_days(monday, friday), 5)

    def test_weekend_is_not_charged(self):
        friday = date(2026, 9, 11)
        monday = date(2026, 9, 14)
        self.assertEqual(service.working_days(friday, monday), 2)

    def test_weekend_only_range_is_zero(self):
        saturday = date(2026, 9, 12)
        self.assertEqual(service.working_days(saturday, saturday + timedelta(days=1)), 0)

    def test_inverted_range_is_zero(self):
        self.assertEqual(service.working_days(date(2026, 9, 11), date(2026, 9, 7)), 0)


class ValidationTest(LeaveTestBase):
    def test_accepts_a_valid_range(self):
        start = self.monday()
        days = service.validate_request(
            self.company, self.emp, self.casual, start, start + timedelta(days=2), False
        )
        self.assertEqual(days, Decimal("3.0"))

    def test_rejects_inverted_range(self):
        start = self.monday()
        with self.assertRaisesMessage(ValidationError, "End date"):
            service.validate_request(
                self.company, self.emp, self.casual, start, start - timedelta(days=2), False
            )

    def test_rejects_past_start(self):
        past = timezone.localdate() - timedelta(days=7)
        with self.assertRaisesMessage(ValidationError, "past"):
            service.validate_request(self.company, self.emp, self.casual, past, past, False)

    def test_rejects_overlapping_request(self):
        start = self.monday()
        self.make_request(start=start, end=start + timedelta(days=1))
        with self.assertRaisesMessage(ValidationError, "already have leave"):
            service.validate_request(
                self.company, self.emp, self.casual, start, start + timedelta(days=1), False
            )

    def test_overlap_ignores_rejected_request(self):
        start = self.monday()
        self.make_request(start=start, status="rejected")
        days = service.validate_request(
            self.company, self.emp, self.casual, start, start, False
        )
        self.assertEqual(days, Decimal("1.0"))

    def test_over_the_consecutive_cap_becomes_unpaid(self):
        """A spell past the cap is charged unpaid, not refused.

        The cap is a limit on *paid* days in one unbroken run, so a 5 working
        day request under a 3-day cap is 3 paid and 2 unpaid rather than an
        error. Blocking it outright was the old behaviour and it is the thing
        this change exists to remove: the applicant gets their dates, and the
        payroll cost lands where it belongs.
        """
        start = self.monday()
        result = service.validate_and_split(
            self.company, self.emp, self.casual, start, start + timedelta(days=6), False
        )
        self.assertEqual(result["days"], Decimal("5.0"))
        self.assertEqual(result["paid"], Decimal("3.0"))
        self.assertEqual(result["unpaid"], Decimal("2.0"))
        self.assertTrue(any("unpaid" in r for r in result["reasons"]))

    def test_beyond_the_annual_allowance_becomes_unpaid(self):
        start = self.monday(weeks=20)
        # 12 days a year, three at a time: four full spells use the allowance.
        for i in range(4):
            begin = start + timedelta(days=i * 21)
            service.validate_and_split(
                self.company, self.emp, self.casual,
                begin, begin + timedelta(days=2), False,
            )
            self.make_request(start=begin, end=begin + timedelta(days=2), days=Decimal("3.0"))

        # Nothing paid is left, so the next request is entirely unpaid.
        begin = start + timedelta(days=21 * 4)
        result = service.validate_and_split(
            self.company, self.emp, self.casual, begin, begin + timedelta(days=2), False
        )
        self.assertEqual(result["days"], Decimal("3.0"))
        self.assertEqual(result["paid"], Decimal("0.0"))
        self.assertEqual(result["unpaid"], Decimal("3.0"))

    def test_pending_leave_counts_against_the_balance(self):
        # Four pending 3-day spells use the whole 12-day allowance.
        base = self.first_monday()
        if base.year != timezone.localdate().year:
            self.skipTest("Not enough of this calendar year left to run this test.")
        for i in range(4):
            begin = base + timedelta(days=i * 7)
            self.make_request(
                start=begin, end=begin + timedelta(days=2), days=Decimal("3.0")
            )

        balance = service.balance_for(self.company, self.emp, self.casual)
        self.assertEqual(balance["approved"], Decimal("0.0"))
        self.assertEqual(balance["pending"], Decimal("12.0"))
        self.assertEqual(balance["remaining"], Decimal("0"))

        # Nothing is approved, yet there is no room left: pending reserves it.
        # The applicant still gets the leave -- it is just not paid.
        result = service.validate_and_split(
            self.company, self.emp, self.casual,
            base + timedelta(days=28), base + timedelta(days=28), True,
        )
        self.assertEqual(result["days"], Decimal("0.5"))
        self.assertEqual(result["paid"], Decimal("0.0"))
        self.assertEqual(result["unpaid"], Decimal("0.5"))

    def test_unlimited_policy_has_no_cap(self):
        start = self.monday()
        end = start + timedelta(days=30)
        days = service.validate_request(
            self.company, self.emp, self.unpaid, start, end, False
        )
        self.assertEqual(days, service.working_days(start, end))
        # Sanity check on the charge: 31 days from a Monday is 4 full weeks
        # (20 weekdays) plus Mon-Wed (3).
        self.assertEqual(days, Decimal("23"))

    def test_half_day_charges_half(self):
        start = self.monday()
        days = service.validate_request(
            self.company, self.emp, self.casual, start, start, True
        )
        self.assertEqual(days, Decimal("0.5"))

    def test_half_day_must_be_a_single_date(self):
        start = self.monday()
        with self.assertRaisesMessage(ValidationError, "single date"):
            service.validate_request(
                self.company, self.emp, self.casual, start, start + timedelta(days=1), True
            )

    def test_weekend_only_range_rejected(self):
        saturday = self.monday() + timedelta(days=5)
        with self.assertRaisesMessage(ValidationError, "weekend only"):
            service.validate_request(
                self.company, self.emp, self.casual, saturday, saturday + timedelta(days=1), False
            )


class BalanceTest(LeaveTestBase):
    def test_half_day_leaves_half_a_day(self):
        start = self.monday()
        self.make_request(start=start, half=True, days=Decimal("0.5"), status="approved")
        balance = service.balance_for(self.company, self.emp, self.casual)
        self.assertEqual(balance["remaining"], Decimal("11.5"))
        self.assertEqual(balance["remaining_label"], "11.5")
        self.assertEqual(balance["approved"], Decimal("0.5"))

    def test_ten_whole_days_do_not_render_scientifically(self):
        for i in range(3):
            start = self.monday() + timedelta(days=i * 7)
            self.make_request(
                start=start, end=start + timedelta(days=2), days=Decimal("3.0"),
                status="approved",
            )
        start = self.monday() + timedelta(days=28)
        self.make_request(
            start=start, end=start, days=Decimal("1.0"), status="approved"
        )
        balance = service.balance_for(self.company, self.emp, self.casual)
        self.assertEqual(balance["approved_label"], "10")

    def test_cancelled_and_rejected_do_not_consume(self):
        start = self.monday()
        self.make_request(start=start, days=Decimal("3.0"), status="cancelled")
        self.make_request(start=start + timedelta(days=7), days=Decimal("3.0"), status="rejected")
        balance = service.balance_for(self.company, self.emp, self.casual)
        self.assertEqual(balance["remaining"], Decimal("12"))

    def test_allowance_resets_each_calendar_year(self):
        # Exhaust this year's allowance using dates still ahead of us.
        base = self.first_monday()
        probe = base + timedelta(days=28)
        if probe.year != timezone.localdate().year:
            self.skipTest("Not enough of this calendar year left to run this test.")
        for i in range(4):
            begin = base + timedelta(days=i * 7)
            self.make_request(
                start=begin, end=begin + timedelta(days=2), days=Decimal("3.0")
            )
        # This year's allowance is spent, so the probe is charged unpaid --
        # which is the whole point of the change: the days are still granted.
        result = service.validate_and_split(
            self.company, self.emp, self.casual, probe, probe, True
        )
        self.assertEqual(result["paid"], Decimal("0.0"))
        self.assertEqual(result["unpaid"], Decimal("0.5"))

        # Next January the employee has the full allowance again, because the
        # balance is computed per calendar year of the request's start date.
        year = timezone.localdate().year + 1
        balance = service.balance_for(self.company, self.emp, self.casual, year=year)
        self.assertEqual(balance["approved"], Decimal("0.0"))
        self.assertEqual(balance["pending"], Decimal("0.0"))
        self.assertEqual(balance["remaining"], Decimal("12"))

        next_january = date(year, 1, 4)
        while next_january.weekday() != 0:
            next_january += timedelta(days=1)
        days = service.validate_request(
            self.company, self.emp, self.casual, next_january, next_january, False
        )
        self.assertEqual(days, Decimal("1.0"))

    def test_unlimited_reports_none(self):
        balance = service.balance_for(self.company, self.emp, self.unpaid)
        self.assertTrue(balance["is_unlimited"])
        self.assertIsNone(balance["remaining"])


class ApproverPermissionTest(LeaveTestBase):
    def test_flagged_approver_passes(self):
        from apps.leave.actions import is_approver

        self.assertTrue(is_approver(self.approver, self.company))
        self.assertTrue(is_approver(self.owner, self.company))
        self.assertFalse(is_approver(self.emp, self.company))


class OnLeaveTest(LeaveTestBase):
    def test_approved_leave_covers_the_date(self):
        start = self.monday()
        self.make_request(
            user=self.emp, start=start, end=start + timedelta(days=4), status="approved"
        )
        self.assertTrue(service.is_on_leave(self.company, self.emp, start + timedelta(days=2)))
        self.assertFalse(service.is_on_leave(self.company, self.emp, start + timedelta(days=7)))

    def test_pending_leave_does_not_count(self):
        start = self.monday()
        self.make_request(user=self.emp, start=start, status="pending")
        self.assertFalse(service.is_on_leave(self.company, self.emp, start))

    def test_another_persons_leave_does_not_count(self):
        start = self.monday()
        self.make_request(user=self.owner, start=start, status="approved")
        self.assertFalse(service.is_on_leave(self.company, self.emp, start))


class SeedDataTest(TestCase):
    """The seeder must produce leave data the app itself would accept."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_data", "--reset", verbosity=0)

    def test_seeded_requests_respect_caps_and_charges(self):
        from apps.leave.models import LeavePolicy

        self.assertTrue(LeavePolicy.objects.exists())
        self.assertEqual(LeaveRequest.objects.count(), 5)

        for leave in LeaveRequest.objects.select_related("user", "policy"):
            expected = (
                Decimal("0.5") if leave.is_half_day
                else service.working_days(leave.start_date, leave.end_date)
            )
            self.assertEqual(
                leave.days, expected,
                f"{leave.user.username} {leave.policy.name} charge does not match its dates",
            )

            # Re-validating a seeded row is a round trip through
            # `validate_and_split`, so it also proves the stored split is the one
            # the service would arrive at again.
            result = service.validate_and_split(
                leave.company, leave.user, leave.policy,
                leave.start_date, leave.end_date, leave.is_half_day,
                exclude_pk=leave.pk,
            )
            self.assertEqual(result["days"], expected)
            self.assertEqual(
                leave.paid_days + leave.unpaid_days, expected,
                f"{leave.user.username} {leave.policy.name} split does not add up",
            )

    def test_seeded_policies_cover_the_common_types(self):
        from apps.leave.models import LeavePolicy

        names = set(LeavePolicy.objects.values_list("name", flat=True))
        self.assertEqual(names, {"Casual", "Sick", "Unpaid"})
        self.assertIsNone(
            LeavePolicy.objects.get(name="Unpaid").max_days_per_year
        )

    def test_seeded_allowance_is_seventeen_days_at_three_at_a_time(self):
        """The office policy: 12 casual + 5 sick, max 3 consecutive days."""
        from apps.leave.models import LeavePolicy

        def days(name):
            return LeavePolicy.objects.get(name=name).max_days_per_year

        self.assertEqual(days("Casual"), Decimal("12.0"))
        self.assertEqual(days("Sick"), Decimal("5.0"))
        self.assertEqual(days("Casual") + days("Sick"), Decimal("17.0"))
        for name in ("Casual", "Sick"):
            with self.subTest(policy=name):
                self.assertEqual(
                    LeavePolicy.objects.get(name=name).max_consecutive_days,
                    Decimal("3.0"),
                )

    def test_the_spell_cap_counts_days_of_other_policies_too(self):
        """2 casual + 2 sick is a four-day run, so only the first 3 days are paid.

        The run is measured across policy types, because a run is a run: the
        spell cap bounds *paid* days in one unbroken stretch, and swapping from
        casual to sick on the Wednesday does not start a new one.
        """
        from apps.accounts.models import Membership
        from apps.leave.models import LeavePolicy, LeaveRequest

        membership = Membership.objects.get(user__username="dev1")
        company = membership.company
        user = membership.user
        sick = LeavePolicy.objects.get(name="Sick")
        casual = LeavePolicy.objects.get(name="Casual")

        monday = timezone.localdate() + timedelta(days=21)
        monday += timedelta(days=(7 - monday.weekday()) % 7)
        self.assertEqual(monday.weekday(), 0, "test needs a Monday anchor")

        # A two-day casual spell on the Monday and Tuesday, already approved.
        LeaveRequest.objects.create(
            company=company,
            user=user,
            policy=casual,
            start_date=monday,
            end_date=monday + timedelta(days=1),
            days=Decimal("2"),
            status="approved",
        )
        # Two more sick days the following Wednesday and Thursday is a 4-day run,
        # so the spell's second half falls outside the 3 paid-day cap.
        result = service.validate_and_split(
            company, user, sick,
            monday + timedelta(days=2), monday + timedelta(days=3),
            is_half_day=False,
        )
        self.assertEqual(result["days"], Decimal("2.0"))
        self.assertEqual(result["paid"], Decimal("1.0"))
        self.assertEqual(result["unpaid"], Decimal("1.0"))

    def test_a_run_of_three_is_still_allowed(self):
        from apps.accounts.models import Membership
        from apps.leave.models import LeavePolicy

        membership = Membership.objects.get(user__username="dev1")
        monday = timezone.localdate() + timedelta(days=28)
        monday += timedelta(days=(7 - monday.weekday()) % 7)
        days = service.validate_request(
            membership.company, membership.user,
            LeavePolicy.objects.get(name="Casual"),
            monday, monday + timedelta(days=2), is_half_day=False,
        )
        self.assertEqual(days, Decimal("3"))

    def test_four_consecutive_days_are_taken_but_one_is_unpaid(self):
        """A 4-day sick spell under a 3 paid-day cap: 3 paid, 1 unpaid.

        This used to be refused outright with "3 days at a time". A sick spell is
        not a scheduling mistake -- the person is ill -- so refusing the dates
        and making them come back with a shorter request was the wrong answer.
        The cap now prices the spell rather than policing it.
        """
        from apps.accounts.models import Membership
        from apps.leave.models import LeavePolicy

        policy = LeavePolicy.objects.get(name="Sick")
        membership = Membership.objects.get(user__username="dev1")
        start = timezone.localdate() + timedelta(days=14)
        start += timedelta(days=(7 - start.weekday()) % 7)  # land on a Monday
        result = service.validate_and_split(
            membership.company,
            membership.user,
            policy,
            start,
            start + timedelta(days=3),
            is_half_day=False,
        )
        self.assertEqual(result["days"], Decimal("4.0"))
        self.assertEqual(result["paid"], Decimal("3.0"))
        self.assertEqual(result["unpaid"], Decimal("1.0"))

    def test_seeder_marks_an_approver(self):
        from apps.accounts.models import Membership

        self.assertTrue(
            Membership.objects.filter(company__name="Acme Corp", is_leave_approver=True).exists()
        )

    def test_seeding_twice_needs_reset(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("seed_data", verbosity=0, stdout=out)
        self.assertIn("already exists", out.getvalue())

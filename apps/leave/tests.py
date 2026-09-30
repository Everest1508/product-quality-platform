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
                     half=False, days=None, status="pending"):
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
        )


class FormatDaysTest(TestCase):
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

    def test_rejects_beyond_consecutive_cap(self):
        start = self.monday()
        with self.assertRaisesMessage(ValidationError, "capped at 3 days"):
            service.validate_request(
                self.company, self.emp, self.casual, start, start + timedelta(days=6), False
            )

    def test_rejects_beyond_annual_allowance(self):
        start = self.monday(weeks=20)
        # 12 days a year, three at a time: four full spells use the allowance.
        for i in range(4):
            begin = start + timedelta(days=i * 21)
            service.validate_request(
                self.company, self.emp, self.casual,
                begin, begin + timedelta(days=2), False,
            )
            self.make_request(start=begin, end=begin + timedelta(days=2), days=Decimal("3.0"))

        begin = start + timedelta(days=21 * 4)
        with self.assertRaisesMessage(ValidationError, "remaining Casual days"):
            service.validate_request(
                self.company, self.emp, self.casual,
                begin, begin + timedelta(days=2), False,
            )

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
        with self.assertRaisesMessage(ValidationError, "remaining Casual days"):
            service.validate_request(
                self.company, self.emp, self.casual,
                base + timedelta(days=28), base + timedelta(days=28), True,
            )

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
        with self.assertRaisesMessage(ValidationError, "remaining Casual days"):
            service.validate_request(
                self.company, self.emp, self.casual, probe, probe, True
            )

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


class ApplyViewTest(LeaveTestBase):
    def post_apply(self, user, **overrides):
        payload = {
            "policy_id": str(self.casual.pk),
            "start_date": self.monday().isoformat(),
            "reason": "Family thing",
        }
        payload.update(overrides)
        self.client.login(username=user.username, password="pass1234")
        return self.client.post(reverse("leave:apply"), payload)

    def test_member_can_apply(self):
        self.post_apply(self.emp)
        leave = LeaveRequest.objects.get(user=self.emp)
        self.assertEqual(leave.status, "pending")
        self.assertEqual(leave.policy, self.casual)
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_requested").exists())

    def test_viewer_can_apply(self):
        viewer = make_user("viewer", self.company, "viewer")
        self.post_apply(viewer)
        self.assertEqual(LeaveRequest.objects.filter(user=viewer).count(), 1)

    def test_rejects_over_the_consecutive_cap(self):
        response = self.post_apply(
            self.emp,
            start_date=self.monday().isoformat(),
            end_date=(self.monday() + timedelta(days=6)).isoformat(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)
        self.assertContains(response, "capped at 3 days")

    def test_cannot_apply_with_another_companys_policy(self):
        foreign = LeavePolicy.objects.create(
            company=self.other, name="Casual", max_days_per_year=Decimal("5.0")
        )
        self.post_apply(self.emp, policy_id=str(foreign.pk))
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_cannot_apply_in_the_past(self):
        past = (timezone.localdate() - timedelta(days=3)).isoformat()
        self.post_apply(self.emp, start_date=past)
        self.assertEqual(LeaveRequest.objects.count(), 0)


class ApproverPermissionTest(LeaveTestBase):
    def test_flagged_approver_passes(self):
        from apps.leave.views import is_approver

        self.assertTrue(is_approver(self.approver, self.company))
        self.assertTrue(is_approver(self.owner, self.company))
        self.assertFalse(is_approver(self.emp, self.company))

    def test_plain_member_cannot_open_queue(self):
        self.client.login(username="emp", password="pass1234")
        self.assertEqual(self.client.get(reverse("leave:approvals")).status_code, 403)

    def test_plain_member_cannot_decide(self):
        leave = self.make_request()
        self.client.login(username="emp", password="pass1234")
        response = self.client.post(reverse("leave:decision", args=[leave.pk, "approve"]))
        self.assertEqual(response.status_code, 403)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")

    def test_approver_can_open_queue(self):
        self.make_request()
        self.client.login(username="approver", password="pass1234")
        response = self.client.get(reverse("leave:approvals"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["requests"]), 1)

    def test_approver_approves(self):
        leave = self.make_request()
        self.client.login(username="approver", password="pass1234")
        self.client.post(reverse("leave:decision", args=[leave.pk, "approve"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")
        self.assertEqual(leave.decided_by, self.approver)
        self.assertIsNotNone(leave.decided_at)
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_approved").exists())

    def test_approver_rejects_with_note(self):
        leave = self.make_request()
        self.client.login(username="approver", password="pass1234")
        self.client.post(
            reverse("leave:decision", args=[leave.pk, "reject"]), {"note": "Too busy"}
        )
        leave.refresh_from_db()
        self.assertEqual(leave.status, "rejected")
        self.assertEqual(leave.decision_note, "Too busy")

    def test_cannot_decide_twice(self):
        leave = self.make_request(status="approved")
        self.client.login(username="approver", password="pass1234")
        self.client.post(reverse("leave:decision", args=[leave.pk, "reject"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")

    def test_cannot_decide_another_companys_request(self):
        foreign_policy = LeavePolicy.objects.create(
            company=self.other, name="Casual", max_days_per_year=Decimal("5.0")
        )
        leave = LeaveRequest.objects.create(
            company=self.other,
            user=self.outsider,
            policy=foreign_policy,
            start_date=self.monday(),
            end_date=self.monday(),
            days=Decimal("1.0"),
        )
        self.client.login(username="approver", password="pass1234")
        response = self.client.post(reverse("leave:decision", args=[leave.pk, "approve"]))
        self.assertEqual(response.status_code, 404)

    def test_unknown_action_is_rejected(self):
        leave = self.make_request()
        self.client.login(username="approver", password="pass1234")
        self.client.post(reverse("leave:decision", args=[leave.pk, "burn"]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")

    def test_queue_only_shows_own_company(self):
        self.make_request()
        LeaveRequest.objects.create(
            company=self.other,
            user=self.outsider,
            policy=LeavePolicy.objects.create(
                company=self.other, name="Casual", max_days_per_year=Decimal("5.0")
            ),
            start_date=self.monday(),
            end_date=self.monday(),
            days=Decimal("1.0"),
        )
        self.client.login(username="approver", password="pass1234")
        response = self.client.get(reverse("leave:approvals"))
        self.assertEqual(len(response.context["requests"]), 1)


class CancelTest(LeaveTestBase):
    def test_can_withdraw_own_pending(self):
        leave = self.make_request()
        self.client.login(username="emp", password="pass1234")
        self.client.post(reverse("leave:cancel", args=[leave.pk]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "cancelled")

    def test_cannot_withdraw_approved(self):
        leave = self.make_request(status="approved")
        self.client.login(username="emp", password="pass1234")
        self.client.post(reverse("leave:cancel", args=[leave.pk]))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "approved")

    def test_cannot_withdraw_someone_elses(self):
        leave = self.make_request(user=self.owner)
        self.client.login(username="emp", password="pass1234")
        response = self.client.post(reverse("leave:cancel", args=[leave.pk]))
        self.assertEqual(response.status_code, 404)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")


class PolicyAdminTest(LeaveTestBase):
    def test_only_admin_can_edit_policy(self):
        self.client.login(username="emp", password="pass1234")
        response = self.client.post(
            reverse("leave:policy_update", args=[self.casual.pk]),
            {"name": "Casual", "max_days_per_year": "99"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_edit_policy(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("leave:policy_update", args=[self.casual.pk]),
            {"name": "Casual", "max_days_per_year": "20", "max_consecutive_days": "5"},
        )
        self.casual.refresh_from_db()
        self.assertEqual(self.casual.max_days_per_year, Decimal("20"))
        self.assertEqual(self.casual.max_consecutive_days, Decimal("5"))

    def test_blank_means_unlimited(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("leave:policy_update", args=[self.casual.pk]),
            {"name": "Casual", "max_days_per_year": "", "max_consecutive_days": ""},
        )
        self.casual.refresh_from_db()
        self.assertIsNone(self.casual.max_days_per_year)
        self.assertIsNone(self.casual.max_consecutive_days)

    def test_consecutive_cannot_exceed_annual(self):
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("leave:policy_update", args=[self.casual.pk]),
            {"name": "Casual", "max_days_per_year": "2", "max_consecutive_days": "5"},
        )
        self.casual.refresh_from_db()
        self.assertEqual(self.casual.max_consecutive_days, Decimal("3.0"))

    def test_cannot_edit_another_companys_policy(self):
        foreign = LeavePolicy.objects.create(
            company=self.other, name="Casual", max_days_per_year=Decimal("5.0")
        )
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(
            reverse("leave:policy_update", args=[foreign.pk]), {"name": "Hijacked"}
        )
        self.assertEqual(response.status_code, 404)


class MyLeaveViewTest(LeaveTestBase):
    def test_shows_own_requests_only(self):
        self.make_request(user=self.emp)
        self.make_request(user=self.owner)
        self.client.login(username="emp", password="pass1234")
        response = self.client.get(reverse("leave:my_leave"))
        self.assertEqual(len(response.context["requests"]), 1)

    def test_shows_balances_for_each_policy(self):
        self.client.login(username="emp", password="pass1234")
        response = self.client.get(reverse("leave:my_leave"))
        names = [b["policy"].name for b in response.context["balances"]]
        self.assertEqual(names, ["Casual", "Unpaid"])

    def test_no_policies_still_renders(self):
        LeavePolicy.objects.filter(company=self.company).delete()
        self.client.login(username="emp", password="pass1234")
        response = self.client.get(reverse("leave:my_leave"))
        self.assertEqual(response.status_code, 200)


class TeamEditApproverTest(LeaveTestBase):
    def test_admin_can_flag_an_approver(self):
        membership = Membership.objects.get(user=self.emp, company=self.company)
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("accounts:team_edit", args=[membership.pk]),
            {
                "first_name": "",
                "last_name": "",
                "email": "emp@acme.test",
                "discord_id": "",
                "role": "developer",
                "is_leave_approver": "true",
            },
        )
        membership.refresh_from_db()
        self.assertTrue(membership.is_leave_approver)

    def test_unchecking_clears_the_flag(self):
        membership = Membership.objects.get(user=self.approver, company=self.company)
        self.client.login(username="owner", password="pass1234")
        self.client.post(
            reverse("accounts:team_edit", args=[membership.pk]),
            {
                "first_name": "",
                "last_name": "",
                "email": "approver@acme.test",
                "discord_id": "",
                "role": "developer",
            },
        )
        membership.refresh_from_db()
        self.assertFalse(membership.is_leave_approver)


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

            days = service.validate_request(
                leave.company, leave.user, leave.policy,
                leave.start_date, leave.end_date, leave.is_half_day,
                exclude_pk=leave.pk,
            )
            self.assertEqual(days, expected)

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
        """2 casual + 2 sick is a four-day run, and the run is what is capped."""
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
        # Two more sick days the following Wednesday and Thursday is a 4-day run.
        with self.assertRaises(ValidationError) as ctx:
            service.validate_request(
                company, user, sick,
                monday + timedelta(days=2), monday + timedelta(days=3),
                is_half_day=False,
            )
        self.assertIn("4 consecutive days", str(ctx.exception))

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

    def test_four_consecutive_days_are_refused(self):
        from apps.accounts.models import Membership
        from apps.leave.models import LeavePolicy

        policy = LeavePolicy.objects.get(name="Sick")
        membership = Membership.objects.get(user__username="dev1")
        start = timezone.localdate() + timedelta(days=14)
        start += timedelta(days=(7 - start.weekday()) % 7)  # land on a Monday
        with self.assertRaises(ValidationError) as ctx:
            service.validate_request(
                membership.company,
                membership.user,
                policy,
                start,
                start + timedelta(days=3),
                is_half_day=False,
            )
        self.assertIn("3 days at a time", str(ctx.exception))

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


class LeavePageRenderTest(LeaveTestBase):
    """The pages must actually render, partials included."""

    def setUp(self):
        super().setUp()
        self.client.login(username="emp", password="pass1234")

    def test_my_leave_renders(self):
        self.assertEqual(self.client.get(reverse("leave:my_leave")).status_code, 200)

    def test_apply_renders_with_policies(self):
        response = self.client.get(reverse("leave:apply"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Casual")

    def test_apply_renders_without_policies(self):
        LeavePolicy.objects.filter(company=self.company).delete()
        response = self.client.get(reverse("leave:apply"))
        self.assertEqual(response.status_code, 200)

    def test_approvals_render_for_approver(self):
        self.make_request()
        self.client.login(username="approver", password="pass1234")
        response = self.client.get(reverse("leave:approvals"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Casual")

    def test_policies_render_for_admin(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("leave:policies"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "max_days_per_year")
        self.assertContains(response, "No cap")

    def test_policies_render_without_any_policy(self):
        LeavePolicy.objects.filter(company=self.company).delete()
        self.client.login(username="owner", password="pass1234")
        response = self.client.get(reverse("leave:policies"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No leave types")

    def test_pending_partial_renders(self):
        response = self.client.post(
            reverse("leave:apply"),
            {"policy_id": self.casual.pk, "start_date": self.monday().isoformat()},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)

    def test_invalid_htmx_submit_renders_errors_with_400(self):
        self.make_request()
        response = self.client.post(
            reverse("leave:apply"),
            {"policy_id": self.casual.pk, "start_date": self.monday().isoformat()},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "already have leave", status_code=400)

    def test_my_leave_shows_no_epsilon_formatting(self):
        for i in range(3):
            start = self.monday() + timedelta(days=i * 7)
            self.make_request(
                start=start, end=start + timedelta(days=2), days=Decimal("3.0"),
                status="approved",
            )
        start = self.monday() + timedelta(days=28)
        self.make_request(start=start, days=Decimal("1.0"), status="approved")
        response = self.client.get(reverse("leave:my_leave"))
        # 10 approved days must read as "10", never as "1E+1".
        self.assertContains(response, "10 approved")
        self.assertNotIn("E+", response.content.decode())


class PolicyScreenTest(LeaveTestBase):
    """The policy editor has to be *findable*.

    It used to be a <table> whose <thead> advertised "Leave type | Days / year
    | Max per spell | Paid" while every body row was a single
    <td colspan="5"> wrapping a <form> holding its own CSS grid. The header was
    structurally unrelated to the inputs, so nothing said which number box was
    the annual days allowance -- which is the whole point of the page.
    """

    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")

    def screen(self):
        return self.client.get(reverse("leave:policies")).content.decode()

    def test_no_fake_header_row(self):
        """A <thead> that cannot line up with its inputs is worse than none."""
        self.assertNotIn("<th>", self.screen())
        self.assertNotIn('colspan="5"', self.screen())

    def test_every_input_is_labelled(self):
        body = self.screen()
        for field in (
            "name",
            "max_days_per_year",
            "max_consecutive_days",
            "color",
            "is_paid",
        ):
            # <select> too: the colour picker is a select, not a text input.
            inputs = re.findall(
                rf'<(?:input|select)[^>]*name="{field}"', body
            )
            self.assertTrue(inputs, f"no {field} input on the page")
            for tag in inputs:
                control_id = re.search(r'id="([^"]+)"', tag)
                self.assertIsNotNone(control_id, f"{field} input has no id")
                self.assertIn(
                    f'<label for="{control_id.group(1)}"',
                    body,
                    f"{field} input has no label",
                )

    def test_the_days_allowance_is_labelled_in_words(self):
        body = self.screen()
        self.assertIn("Days per year", body)
        self.assertIn("Max per spell", body)
        # "Unlimited" is ambiguous against a real 0 cap, so blank reads "No cap".
        self.assertNotIn("Unlimited", body)
        self.assertGreaterEqual(body.count('placeholder="No cap"'), 2)

    def test_admin_can_add_a_leave_type(self):
        """The empty state always said 'add a leave type' with no way to."""
        response = self.client.post(
            reverse("leave:policy_add"),
            {
                "name": "Sick",
                "max_days_per_year": "8",
                "max_consecutive_days": "2",
                "is_paid": "true",
            },
        )
        self.assertRedirects(response, reverse("leave:policies"))
        sick = LeavePolicy.objects.get(company=self.company, name="Sick")
        self.assertEqual(sick.max_days_per_year, Decimal("8"))
        self.assertTrue(sick.is_paid)

    def test_new_type_defaults_to_unlimited_when_boxes_are_blank(self):
        self.client.post(
            reverse("leave:policy_add"), {"name": "Sabbatical", "is_paid": "true"}
        )
        policy = LeavePolicy.objects.get(company=self.company, name="Sabbatical")
        self.assertIsNone(policy.max_days_per_year)
        self.assertIsNone(policy.max_consecutive_days)

    def test_colour_round_trips_and_paints_the_row(self):
        """`color` is documented as a badge token but was never settable."""
        policy = LeavePolicy.objects.filter(company=self.company).first()
        response = self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {
                "name": policy.name,
                "max_days_per_year": "12",
                "is_paid": "true",
                "color": "green",
            },
        )
        self.assertEqual(response.status_code, 302)
        policy.refresh_from_db()
        self.assertEqual(policy.color, "green")
        # The dot is a class, not an inline style built from user input.
        self.assertIn('class="lp-dot lp-dot-green"', self.screen())

    def test_a_colour_outside_the_closed_set_is_rejected(self):
        """`color` becomes a class name, so free text is style injection."""
        policy = LeavePolicy.objects.filter(company=self.company).first()
        before = policy.color
        self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {
                "name": policy.name,
                "is_paid": "true",
                "color": "red; background:url(https://evil.test/x)",
            },
        )
        policy.refresh_from_db()
        self.assertEqual(policy.color, before)
        self.assertNotIn("background:url", self.screen())

    def test_icon_round_trips_and_renders_inline_svg(self):
        """A <select> cannot hold SVG, so the picker is a grid of radio tiles.

        The glyph is inlined from apps.core.icons, never a remote <img>, so a
        policy page cannot be broken by a third-party host being down.
        """
        policy = LeavePolicy.objects.filter(company=self.company).first()
        self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {
                "name": policy.name,
                "is_paid": "true",
                "icon": "umbrella",
            },
        )
        policy.refresh_from_db()
        self.assertEqual(policy.icon, "umbrella")
        body = self.screen()
        self.assertIn('class="lp-icon-glyph"', body)
        self.assertIn('<path', body)
        self.assertNotIn("<img", body)

    def test_an_icon_outside_the_closed_set_is_rejected(self):
        policy = LeavePolicy.objects.filter(company=self.company).first()
        self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {
                "name": policy.name,
                "is_paid": "true",
                "icon": '<script>alert(1)</script>',
            },
        )
        policy.refresh_from_db()
        # The bad value is dropped, leaving the type with no icon at all.
        self.assertNotIn("<script>", policy.icon)
        self.assertIn(policy.icon, ICON_NAMES | {""})

    def test_a_policy_with_no_icon_renders_no_glyph(self):
        policy = LeavePolicy.objects.filter(company=self.company).first()
        policy.icon = ""
        policy.save()
        self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {"name": policy.name, "is_paid": "true", "icon": ""},
        )
        policy.refresh_from_db()
        self.assertEqual(policy.icon, "")

    def test_render_icon_refuses_anything_outside_the_allowlist(self):
        """Defence in depth: even a caller that skipped clean_icon is safe."""
        self.assertEqual(render_icon("<script>x</script>"), "")
        self.assertEqual(render_icon("../../etc/passwd"), "")
        self.assertEqual(render_icon(""), "")

    def test_every_vendored_icon_is_inert(self):
        """The vendored SVG bodies are markup, so audit them in the suite."""
        for name, body in ICONS.items():
            for bad in ("<script", "onload", "onerror", "onclick", "javascript:",
                        "url(", "xlink:href", "http"):
                self.assertNotIn(bad, body, f"{name} contains {bad!r}")

    def test_blank_colour_is_allowed(self):
        policy = LeavePolicy.objects.filter(company=self.company).first()
        self.client.post(
            reverse("leave:policy_update", args=[policy.pk]),
            {"name": policy.name, "is_paid": "true", "color": ""},
        )
        policy.refresh_from_db()
        self.assertEqual(policy.color, "")

    def test_only_admin_can_add_a_leave_type(self):
        self.client.login(username="emp", password="pass1234")
        response = self.client.post(reverse("leave:policy_add"), {"name": "Sneaky"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            LeavePolicy.objects.filter(company=self.company, name="Sneaky").exists()
        )

    def test_add_form_rejects_a_spell_longer_than_the_allowance(self):
        self.client.post(
            reverse("leave:policy_add"),
            {"name": "Bad", "max_days_per_year": "2", "max_consecutive_days": "5"},
        )
        self.assertFalse(
            LeavePolicy.objects.filter(company=self.company, name="Bad").exists()
        )

    def test_the_add_form_is_always_on_the_page(self):
        body = self.screen()
        self.assertIn(reverse("leave:policy_add"), body)
        self.assertIn('placeholder="e.g. Sick"', body)


class SidebarActiveStateTest(LeaveTestBase):
    """The sidebar used to decide "active" with `'x' in request.path`.

    A substring test lights up every item whose fragment appears anywhere in the
    path, so /attendance/team/ highlighted "My attendance", "Team attendance" and
    "Team" at the same time, and /attendance/timesheet/ highlighted two. Exactly
    one item may be active, and it must be the one you are actually on.
    """

    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")

    def sidebar(self, url):
        body = self.client.get(url, follow=True).content.decode()
        return body[body.index("<aside") : body.index("</aside>")]

    def active_labels(self, url):
        return re.findall(
            r'class="side-item active"[^>]*>\s*<svg.*?'
            r'<span class="side-label">([^<]+)</span>',
            self.sidebar(url),
            re.S,
        )

    def test_exactly_one_item_is_active_per_page(self):
        for url, expected in [
            ("/attendance/", "My attendance"),
            ("/attendance/team/", "Team attendance"),
            ("/attendance/timesheet/", "Timesheet"),
            ("/leave/", "My leave"),
            ("/leave/policies/", "Leave Policy"),
            ("/team/", "Team"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.active_labels(url), [expected])

    def test_the_team_page_does_not_also_light_up_my_attendance(self):
        """The exact regression: a shared path fragment lit up two items."""
        labels = self.active_labels("/attendance/team/")
        self.assertNotIn("My attendance", labels)
        self.assertNotIn("Team", labels)

    def test_active_item_is_marked_with_aria_current(self):
        for url in ("/leave/", "/leave/policies/", "/attendance/team/"):
            with self.subTest(url=url):
                bar = self.sidebar(url)
                self.assertEqual(bar.count('aria-current="page"'), 1)

    def test_every_nav_item_carries_an_icon_and_a_label(self):
        bar = self.sidebar("/leave/")
        items = [c for c in re.split(r"(?=<a )", bar) if "side-item" in c]
        self.assertTrue(items)
        for item in items:
            self.assertIn('<svg class="ic"', item)
            self.assertIn("side-label", item)
            # Collapsed sidebar hides the label with `clip`, not `display:none`,
            # so `data-label` is the hover tooltip and the text is still readable.
            self.assertIn("data-label=", item)

    def test_no_hand_rolled_svg_is_left_in_the_sidebar(self):
        """All glyphs come from apps.core.icons so they share one stroke set."""
        bar = self.sidebar("/leave/")
        self.assertNotIn('<svg class="ic" viewBox="0 0 24 24"><path', bar)

    def test_an_icon_named_in_the_template_actually_exists(self):
        """A typo in `{% icon %}` renders nothing at all -- silently."""
        template = Path(settings.BASE_DIR / "templates/core/_sidebar.html").read_text()
        for name in re.findall(r"\{% icon '([a-z0-9-]+)'", template):
            with self.subTest(icon=name):
                self.assertIn(name, ICON_NAMES)

    def test_no_page_is_left_with_nothing_highlighted(self):
        """Every page a member can reach must resolve to one nav item.

        Audited against the whole URLconf, not the handful of pages that
        happened to be visited. Seven were orphaned: the apply-leave form
        (the condition named `leave:leave_create`, a route that has never
        existed -- it is called `apply`), the survey list and its create page,
        the whole automation section, and the payroll Holidays tab. All of
        them rendered a sidebar with nothing marked, so the nav read as though
        the app had fewer pages than it has.
        """
        for url, expected in [
            ("/leave/apply/", "My leave"),
            ("/feedback/", "All feedback"),
            ("/feedback/create/", "All feedback"),
            ("/feedback/cs-hub/", "CS Hub"),
            ("/automation/", "All automation"),
            ("/automation/create/", "All automation"),
            ("/payroll/holidays/", "Payroll"),
            ("/payroll/preview/", "Payroll"),
            ("/payroll/me/", "My payslips"),
            ("/dsr/", "DSR Sheet"),
            ("/leave/approvals/", "Leave approvals"),
            ("/tickets/kanban/", "All tickets"),
            ("/errors/create/", "All errors"),
            ("/products/create/", "Products"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.active_labels(url), [expected])

    def test_the_main_column_is_not_swallowed_by_the_sidebar(self):
        """The sidebar must close before the main column opens.

        A stray `</div>` inside `_sidebar.html` closed the `<aside>` early, so
        `<div class="main">` was parsed *inside* it. `.shell` is a two-column
        grid, so the fixed-width sidebar then clipped the entire page: the nav
        rendered and everything right of it was blank white. No view error, no
        bad CSS, no stale cache -- the HTML itself was malformed.

        So assert the invariant rather than the symptom: every tag balances, and
        `.main` is a sibling of the sidebar, not a descendant.
        """
        VOID = {
            "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
            "meta", "param", "source", "track", "wbr", "path", "circle", "rect",
            "line", "polyline", "polygon", "ellipse", "use", "stop",
        }
        for url in ["/", "/leave/", "/attendance/", "/payroll/me/", "/team/"]:
            with self.subTest(url=url):
                page = self.client.get(url, follow=True).content.decode()
                # <script>/<style> hold text, not markup: tokenizing them turns
                # a CSS selector or a JS comparison into phantom tags.
                body = re.sub(r"<script\b.*?</script>", "", page, flags=re.S | re.I)
                body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S | re.I)
                open_body = body.index("<body")
                body = body[open_body + body[open_body:].index(">") + 1 :]
                body = body[: body.rindex("</body")]

                stack = []
                for match in re.finditer(r"<(/?)([a-zA-Z0-9]+)([^>]*?)(/?)>", body):
                    closing, tag, _, self_closing = match.groups()
                    tag = tag.lower()
                    if tag in VOID or self_closing:
                        continue
                    if closing:
                        self.assertTrue(
                            stack and stack[-1] == tag,
                            f"</{tag}> closes nothing (innermost is "
                            f"{stack[-1] if stack else None}) at offset {match.start()}",
                        )
                        stack.pop()
                    else:
                        stack.append(tag)
                self.assertEqual(stack, [], f"unclosed tags on {url}: {stack}")

                aside_open = body.index("<aside")
                aside_close = body.index("</aside>")
                main_at = body.index('class="main"')
                self.assertLess(
                    aside_close, main_at,
                    'class="main" sits inside the <aside>, so the grid cannot '
                    "give it a column of its own",
                )
                self.assertGreater(aside_open, -1)

    def test_the_settings_page_marks_the_user_menu_instead(self):
        """It has no nav item, so the menu link carries the state.

        A 404-free page with zero `aria-current` reads as "you are nowhere",
        which is how the orphaned pages above were spotted in the first place.
        """
        bar = self.sidebar("/profile/")
        self.assertEqual(self.active_labels("/profile/"), [])
        self.assertEqual(bar.count('aria-current="page"'), 1)
        self.assertIn('aria-current="page"', bar.split("side-user-menu")[1])

    def test_every_nav_landmark_is_named(self):
        """Four `<nav>` elements with no `aria-label` are four identical
        "navigation" entries in a screen reader's landmark list."""
        bar = self.sidebar("/leave/")
        navs = re.findall(r"<nav\b[^>]*>", bar)
        self.assertGreaterEqual(len(navs), 3)
        for nav in navs:
            with self.subTest(nav=nav):
                self.assertIn("aria-label=", nav)

    def test_nav_links_have_exactly_one_tooltip_source(self):
        """`data-label` already drives the collapsed hover tooltip.

        A `title` alongside it means the browser draws its own tooltip on top of
        the styled one, so hovering a collapsed item flashes two labels.
        """
        bar = self.sidebar("/leave/")
        # The opening tag only: a chunk split on `<a ` runs on past the closing
        # </nav> to the collapse *button*, and a button legitimately has a title.
        tags = re.findall(r"<a\b[^>]*class=\"side-item[^>]*>", bar)
        self.assertTrue(tags)
        for tag in tags:
            with self.subTest(tag=tag[:60]):
                self.assertIn("data-label=", tag)
                self.assertNotIn("title=", tag)

    def test_the_active_bar_and_the_collapsed_tooltip_are_not_clipped(self):
        """`.side-item` must not clip its own pseudo-elements.

        Both live *outside* the item's box -- the bar at `left:-8px`, the
        tooltip at `left:100%+12px` -- so an `overflow:hidden` on the item
        swallowed them. The bar vanished exactly when the sidebar is collapsed
        and the tooltip never appeared at all, which left a collapsed nav of
        unlabelled icons. The label ellipsises via `.side-label`, which is where
        the clipping belongs.
        """
        css = Path(settings.BASE_DIR / "templates/core/base.html").read_text()
        rule = re.search(r"\.side-item\{[^}]*\}", css)
        self.assertIsNotNone(rule)
        self.assertNotIn("overflow:hidden", rule.group(0))
        label_rule = re.search(r"\.side-item \.side-label\{[^}]*\}", css)
        self.assertIn("overflow:hidden", label_rule.group(0))
        self.assertIn("min-width:0", label_rule.group(0))

    def test_sections_are_divided_in_both_states(self):
        """Separators used to be collapsed-only, so the nav looked structured in
        one state and flat in the other."""
        css = Path(settings.BASE_DIR / "templates/core/base.html").read_text()
        separator = re.search(r"\.nav-section \+ \.nav-section\{[^}]*\}", css)
        self.assertIsNotNone(separator)
        self.assertIn("border-top", separator.group(0))
        # Not parked inside the collapsed media query any more.
        self.assertNotIn(
            "html.sidebar-collapsed .nav-section + .nav-section", css
        )

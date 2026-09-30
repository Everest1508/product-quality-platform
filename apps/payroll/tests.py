from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.payroll import service
from apps.payroll.models import Holiday, Payslip, PayrollProfile, PayrollRun

User = get_user_model()


def make_user(username, company, role="developer"):
    user = User.objects.create_user(username, f"{username}@test.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class CycleBoundsTest(TestCase):
    def test_cycle_starts_on_the_27th(self):
        start, end = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(start, date(2026, 10, 27))
        self.assertEqual(end, date(2026, 11, 26))

    def test_day_27_belongs_to_the_new_cycle(self):
        self.assertEqual(
            service.cycle_bounds(date(2026, 10, 27)),
            (date(2026, 10, 27), date(2026, 11, 26)),
        )

    def test_day_26_belongs_to_the_previous_cycle(self):
        self.assertEqual(
            service.cycle_bounds(date(2026, 10, 26)),
            (date(2026, 9, 27), date(2026, 10, 26)),
        )

    def test_anchor_is_always_inside_its_cycle(self):
        for day in range(1, 29):
            for month in (1, 2, 3, 6, 9, 12):
                if day > 28 and month == 2:
                    continue
                anchor = date(2026, month, day)
                start, end = service.cycle_bounds(anchor)
                self.assertLessEqual(start, anchor, f"{anchor} before its cycle")
                self.assertLessEqual(anchor, end, f"{anchor} after its cycle")
                self.assertEqual(start.day, 27)
                self.assertEqual(end.day, 26)

    def test_cycles_do_not_overlap(self):
        """The point of ending on the 26th: no day is paid twice."""
        start, end = service.cycle_bounds(date(2026, 10, 27))
        next_start, next_end = service.shift_cycle(start, 1)
        self.assertLessEqual(end, next_start)
        self.assertEqual(end + timedelta(days=1), next_start)

    def test_shift_cycle(self):
        self.assertEqual(
            service.shift_cycle(date(2026, 10, 27), 1),
            (date(2026, 11, 27), date(2026, 12, 26)),
        )
        self.assertEqual(
            service.shift_cycle(date(2026, 10, 27), -1),
            (date(2026, 9, 27), date(2026, 10, 26)),
        )

    def test_cycle_crosses_the_year(self):
        self.assertEqual(
            service.cycle_bounds(date(2027, 1, 5)),
            (date(2026, 12, 27), date(2027, 1, 26)),
        )


class PayrollTestBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make_user("owner", self.company, "owner")
        self.dev = make_user("dev", self.company)
        self.bot = make_user("bot", self.company, "viewer")

        self.casual = LeavePolicy.objects.create(
            company=self.company, name="Casual", is_paid=True,
            max_days_per_year=Decimal("12.0"),
        )
        self.unpaid = LeavePolicy.objects.create(
            company=self.company, name="Unpaid", is_paid=False,
        )
        self.start = date(2026, 10, 27)
        self.end = date(2026, 11, 26)

    def profile(self, user, rate="1200.00", on_payroll=True, company=None,
                effective_from=None):
        return PayrollProfile.objects.create(
            company=company or self.company,
            user=user,
            daily_rate=Decimal(rate),
            is_on_payroll=on_payroll,
            effective_from=effective_from or date(2026, 1, 1),
        )

    def leave(self, user, start, end, policy, status="approved", half=False):
        return LeaveRequest.objects.create(
            company=self.company,
            user=user,
            policy=policy,
            start_date=start,
            end_date=end,
            is_half_day=half,
            days=Decimal("0.5") if half else Decimal(
                str(len(service._weekdays(start, end)))
            ),
            status=status,
        )


class WorkingDaysTest(PayrollTestBase):
    def test_weekends_are_excluded(self):
        # 27 Oct 2026 (Tue) to 26 Nov 2026 (Thu) is 23 weekdays.
        self.assertEqual(
            service.working_days(self.company, self.start, self.end), 23
        )

    def test_holidays_are_excluded(self):
        Holiday.objects.create(
            company=self.company, date=date(2026, 10, 28), name="Diwali"
        )
        self.assertEqual(
            service.working_days(self.company, self.start, self.end), 22
        )

    def test_another_companys_holiday_does_not_count(self):
        Holiday.objects.create(
            company=self.other, date=date(2026, 10, 28), name="Diwali"
        )
        self.assertEqual(
            service.working_days(self.company, self.start, self.end), 23
        )

    def test_a_holiday_on_a_weekend_does_not_double_count(self):
        """Saturday is already off; the day count must not go negative."""
        Holiday.objects.create(
            company=self.company, date=date(2026, 10, 31), name="Sat"
        )
        self.assertEqual(
            service.working_days(self.company, self.start, self.end), 23
        )

    def test_inverted_range_is_zero(self):
        self.assertEqual(service.working_days(self.company, self.end, self.start), 0)

    def test_working_day_list_skips_weekends_and_holidays(self):
        Holiday.objects.create(
            company=self.company, date=date(2026, 10, 28), name="Diwali"
        )
        days = service.working_day_list(self.company, self.start, self.end)
        self.assertNotIn(date(2026, 10, 28), days)
        self.assertNotIn(date(2026, 10, 31), days)
        self.assertIn(date(2026, 10, 27), days)
        self.assertEqual(len(days), 22)


class LeaveInPeriodTest(PayrollTestBase):
    def test_paid_leave_is_counted_separately(self):
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.casual)
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["paid_days"], Decimal("3.00"))
        self.assertEqual(result["unpaid_days"], Decimal("0.00"))

    def test_unpaid_leave_is_deducted(self):
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["unpaid_days"], Decimal("3.00"))

    def test_pending_leave_does_not_reduce_pay(self):
        self.leave(
            self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid, status="pending"
        )
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["unpaid_days"], Decimal("0.00"))

    def test_half_day_charges_half(self):
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 2), self.unpaid, half=True)
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["unpaid_days"], Decimal("0.5"))

    def test_leave_is_split_across_two_cycles(self):
        """25 Oct - 4 Nov straddles the 27th, so the days must be clipped."""
        request = self.leave(
            self.dev, date(2026, 10, 23), date(2026, 11, 4), self.unpaid
        )
        first = service.leave_days_in_period(
            self.company, self.dev, date(2026, 9, 27), date(2026, 10, 26)
        )
        second = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        # 23, 26 Oct (2) land in the first cycle; 27 Oct - 4 Nov (7) in the second.
        self.assertEqual(first["unpaid_days"], Decimal("2.00"))
        self.assertEqual(second["unpaid_days"], Decimal("7.00"))
        # And the two together equal the request's own charge.
        self.assertEqual(
            first["unpaid_days"] + second["unpaid_days"], request.days
        )

    def test_leave_outside_the_cycle_is_ignored(self):
        self.leave(self.dev, date(2026, 8, 3), date(2026, 8, 7), self.unpaid)
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["unpaid_days"], Decimal("0.00"))

    def test_leave_covering_a_holiday_is_not_charged(self):
        """A holiday is already unpaid-free; deducting for it double-penalises."""
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        # 2-4 Nov is 3 weekdays, but 2 Nov is the holiday, so only 2 are charged.
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["unpaid_days"], Decimal("2.00"))

    def test_holiday_and_leave_reach_the_same_total(self):
        """Payable days must not fall below the cycle's own working days."""
        self.profile(self.dev, "1000.00")
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        _, rows = service.preview(self.company, self.start, self.end)
        # 22 working days (holiday excluded) - 2 charged leave days.
        self.assertEqual(rows[0]["payable_days"], Decimal("20.00"))
        self.assertEqual(rows[0]["deduction"], Decimal("2000.00"))


class CalculationTest(PayrollTestBase):
    def test_full_month_with_no_leave(self):
        self.profile(self.dev, "1200.00")
        working, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(working, 23)
        self.assertEqual(rows[0]["payable_days"], Decimal("23.00"))
        self.assertEqual(rows[0]["gross"], Decimal("27600.00"))
        self.assertEqual(rows[0]["deduction"], Decimal("0.00"))

    def test_unpaid_leave_reduces_gross(self):
        self.profile(self.dev, "1200.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        _, rows = service.preview(self.company, self.start, self.end)
        # 23 working days - 3 unpaid = 20 payable.
        self.assertEqual(rows[0]["payable_days"], Decimal("20.00"))
        self.assertEqual(rows[0]["deduction"], Decimal("3600.00"))
        self.assertEqual(rows[0]["gross"], Decimal("24000.00"))

    def test_paid_leave_does_not_reduce_gross(self):
        self.profile(self.dev, "1200.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.casual)
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["payable_days"], Decimal("23.00"))
        self.assertEqual(rows[0]["deduction"], Decimal("0.00"))
        self.assertEqual(rows[0]["gross"], Decimal("27600.00"))

    def test_mixed_paid_and_unpaid(self):
        self.profile(self.dev, "1000.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 3), self.casual)
        self.leave(self.dev, date(2026, 11, 9), date(2026, 11, 10), self.unpaid)
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["paid_leave_days"], Decimal("2.00"))
        self.assertEqual(rows[0]["unpaid_leave_days"], Decimal("2.00"))
        self.assertEqual(rows[0]["payable_days"], Decimal("21.00"))
        self.assertEqual(rows[0]["gross"], Decimal("21000.00"))

    def test_holiday_reduces_working_days(self):
        self.profile(self.dev, "1000.00")
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        working, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(working, 22)
        self.assertEqual(rows[0]["gross"], Decimal("22000.00"))

    def test_half_day_unpaid_deducts_half_a_day(self):
        self.profile(self.dev, "1000.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 2), self.unpaid, half=True)
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["payable_days"], Decimal("22.5"))
        self.assertEqual(rows[0]["deduction"], Decimal("500.00"))

    def test_payable_never_goes_negative(self):
        self.profile(self.dev, "1000.00")
        self.leave(
            self.dev, date(2026, 10, 27), date(2026, 11, 26), self.unpaid
        )
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["payable_days"], Decimal("0.00"))
        self.assertEqual(rows[0]["gross"], Decimal("0.00"))

    def test_absent_days_are_still_paid(self):
        """Only unpaid leave deducts; an un-punched day is not a deduction."""
        self.profile(self.dev, "1000.00")
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["payable_days"], Decimal("23.00"))


class WhoIsPaidTest(PayrollTestBase):
    def test_only_people_on_payroll_are_included(self):
        self.profile(self.dev, "1000.00")
        self.profile(self.bot, "500.00", on_payroll=False)
        users = [p.user for p in service.payable_people(self.company, self.start)]
        self.assertEqual(users, [self.dev])

    def test_someone_with_no_profile_is_skipped(self):
        self.profile(self.dev, "1000.00")
        users = [p.user for p in service.payable_people(self.company, self.start)]
        self.assertNotIn(self.owner, users)

    def test_another_companys_profile_does_not_leak(self):
        self.profile(self.bot, "500.00", company=self.other)
        users = [p.user for p in service.payable_people(self.company, self.start)]
        self.assertEqual(users, [])

    def test_future_rate_is_ignored(self):
        self.profile(
            self.dev, "1000.00", effective_from=date(2026, 12, 1)
        )
        self.assertEqual(
            service.payable_people(self.company, self.start), []
        )

    def test_latest_rate_wins(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 1, 1))
        self.profile(self.dev, "1500.00", effective_from=date(2026, 10, 27))
        active = service.active_profile(self.company, self.dev, self.start)
        self.assertEqual(active.daily_rate, Decimal("1500.00"))

    def test_unticking_removes_someone(self):
        self.profile(self.dev, "1000.00")
        self.profile(
            self.dev, "1000.00", on_payroll=False, effective_from=date(2026, 11, 1)
        )
        self.assertEqual(service.payable_people(self.company, self.start)[0].user, self.dev)
        self.assertEqual(
            service.payable_people(self.company, date(2026, 11, 5)), []
        )


class RunTest(PayrollTestBase):
    def test_generate_creates_one_payslip_per_person(self):
        self.profile(self.dev, "1000.00")
        self.profile(self.bot, "500.00", on_payroll=False)
        run, created = service.generate_run(self.company, self.start, self.end)
        self.assertTrue(created)
        self.assertEqual(run.payslips.count(), 1)
        self.assertEqual(run.working_days, 23)
        self.assertEqual(run.total_gross, Decimal("23000.00"))

    def test_generate_is_idempotent(self):
        self.profile(self.dev, "1000.00")
        service.generate_run(self.company, self.start, self.end)
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(PayrollRun.objects.count(), 1)
        self.assertEqual(run.payslips.count(), 1)

    def test_regenerating_after_a_new_holiday_updates_pay(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(run.total_gross, Decimal("23000.00"))
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        run, created = service.generate_run(self.company, self.start, self.end)
        self.assertTrue(created)
        self.assertEqual(run.total_gross, Decimal("22000.00"))

    def test_locked_run_is_not_regenerated(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        run.is_locked = True
        run.save()
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        same_run, created = service.generate_run(self.company, self.start, self.end)
        self.assertFalse(created)
        self.assertEqual(same_run.total_gross, Decimal("23000.00"))

    def test_payslips_are_a_snapshot(self):
        """Editing a rate afterwards must not rewrite an issued payslip."""
        self.profile(self.dev, "1000.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        run, _ = service.generate_run(self.company, self.start, self.end)
        payslip = run.payslips.get()
        self.assertEqual(payslip.gross, Decimal("20000.00"))

        # Retroactively change everything the payslip was built from: a raise
        # dated before the cycle, and the leave being cancelled.
        self.profile(self.dev, "5000.00", effective_from=date(2026, 2, 1))
        LeaveRequest.objects.update(status="cancelled")
        payslip.refresh_from_db()
        self.assertEqual(payslip.gross, Decimal("20000.00"))
        self.assertEqual(payslip.daily_rate, Decimal("1000.00"))

    def test_generating_logs_activity(self):
        from apps.dashboards.models import ActivityLog

        self.profile(self.dev, "1000.00")
        service.generate_run(
            self.company, self.start, self.end, created_by=self.owner
        )
        self.assertTrue(
            ActivityLog.objects.filter(event_type="payroll_run").exists()
        )


class PayrollAccessTest(PayrollTestBase):
    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1000.00")
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.payslip = self.run.payslips.get()

    def test_admin_can_open_everything(self):
        self.client.login(username="owner", password="pass1234")
        for url in (
            reverse("payroll:run_list"),
            reverse("payroll:preview"),
            reverse("payroll:profiles"),
            reverse("payroll:holidays"),
            reverse("payroll:run_detail", args=[self.run.pk]),
            reverse("payroll:payslip", args=[self.payslip.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_developer_is_locked_out(self):
        self.client.login(username="dev", password="pass1234")
        for url in (
            reverse("payroll:run_list"),
            reverse("payroll:preview"),
            reverse("payroll:profiles"),
            reverse("payroll:holidays"),
            reverse("payroll:run_detail", args=[self.run.pk]),
            reverse("payroll:payslip", args=[self.payslip.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_developer_cannot_generate(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.post(reverse("payroll:preview"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PayrollRun.objects.count(), 1)

    def test_cannot_view_another_companys_payslip(self):
        self.client.login(username="owner", password="pass1234")
        other_run = PayrollRun.objects.create(
            company=self.other, period_start=self.start, period_end=self.end
        )
        other_slip = Payslip.objects.create(
            company=self.other, run=other_run, user=self.bot,
            daily_rate=Decimal("100.00"), gross=Decimal("100.00"),
        )
        self.assertEqual(
            self.client.get(reverse("payroll:payslip", args=[other_slip.pk])).status_code,
            404,
        )

    def test_cannot_delete_another_companys_holiday(self):
        holiday = Holiday.objects.create(
            company=self.other, date=date(2026, 11, 2), name="X"
        )
        self.client.login(username="owner", password="pass1234")
        self.client.post(reverse("payroll:holiday_delete", args=[holiday.pk]))
        self.assertTrue(Holiday.objects.filter(pk=holiday.pk).exists())


class PayrollViewTest(PayrollTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")

    def test_preview_shows_numbers(self):
        self.profile(self.dev, "1000.00")
        response = self.client.get(reverse("payroll:preview"), {"cycle": "2026-10-27"})
        self.assertEqual(response.context["working_days"], 23)
        self.assertContains(response, "23000.00")

    def test_preview_defaults_to_the_cycle_running_today(self):
        """No date in the URL means the cycle containing today, not a fixed one."""
        self.profile(self.dev, "1000.00")
        response = self.client.get(reverse("payroll:preview"))
        expected_start, expected_end = service.cycle_bounds(date.today())
        self.assertEqual(response.context["period_start"], expected_start)
        self.assertEqual(response.context["period_end"], expected_end)

    def test_generate_from_the_preview_screen(self):
        self.profile(self.dev, "1000.00")
        self.client.post(reverse("payroll:preview"))
        self.assertEqual(PayrollRun.objects.count(), 1)
        self.assertEqual(Payslip.objects.count(), 1)

    def test_run_label_is_readable(self):
        self.assertEqual(
            PayrollRun(
                period_start=date(2026, 10, 27), period_end=date(2026, 11, 26)
            ).label,
            "27 Oct 2026 → 26 Nov 2026",
        )

    def test_lock_toggles(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.client.post(reverse("payroll:run_lock", args=[run.pk]))
        run.refresh_from_db()
        self.assertTrue(run.is_locked)
        self.client.post(reverse("payroll:run_lock", args=[run.pk]))
        run.refresh_from_db()
        self.assertFalse(run.is_locked)

    def test_add_holiday(self):
        response = self.client.post(
            reverse("payroll:holidays"),
            {"date": "2026-11-02", "name": "Diwali"},
        )
        self.assertRedirects(response, reverse("payroll:holidays"))
        self.assertTrue(
            Holiday.objects.filter(company=self.company, name="Diwali").exists()
        )

    def test_duplicate_holiday_is_rejected(self):
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        self.client.post(
            reverse("payroll:holidays"), {"date": "2026-11-02", "name": "Again"}
        )
        self.assertEqual(Holiday.objects.filter(date=date(2026, 11, 2)).count(), 1)

    def test_set_rate_for_someone(self):
        membership = Membership.objects.get(user=self.dev, company=self.company)
        self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": membership.pk,
                "daily_rate": "1500.00",
                "currency": "INR",
                "effective_from": "2026-01-01",
                "is_on_payroll": "on",
            },
        )
        profile = PayrollProfile.objects.get(user=self.dev)
        self.assertEqual(profile.daily_rate, Decimal("1500.00"))
        self.assertTrue(profile.is_on_payroll)

    def test_saving_the_same_date_edits_rather_than_duplicates(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 1, 1))
        membership = Membership.objects.get(user=self.dev, company=self.company)
        self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": membership.pk,
                "daily_rate": "2500.00",
                "currency": "INR",
                "effective_from": "2026-01-01",
                "is_on_payroll": "on",
            },
        )
        profile = PayrollProfile.objects.get(user=self.dev)
        self.assertEqual(profile.daily_rate, Decimal("2500.00"))
        self.assertEqual(PayrollProfile.objects.filter(user=self.dev).count(), 1)

    def test_unticking_removes_from_the_next_run(self):
        self.profile(self.dev, "1000.00")
        membership = Membership.objects.get(user=self.dev, company=self.company)
        self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": membership.pk,
                "daily_rate": "1000.00",
                "currency": "INR",
                "effective_from": "2026-01-01",
            },
        )
        _, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows, [])

    def test_profiles_page_lists_every_member(self):
        response = self.client.get(reverse("payroll:profiles"))
        self.assertEqual(len(response.context["rows"]), 3)

    def test_profiles_page_posts_the_membership_for_this_company(self):
        """The hidden pk must be this company's membership, not another one."""
        response = self.client.get(reverse("payroll:profiles"))
        row = next(r for r in response.context["rows"] if r["user"] == self.dev)
        self.assertEqual(row["membership"].company, self.company)
        self.assertContains(response, f'value="{row["membership"].pk}"')

    def test_cannot_set_a_rate_through_another_companys_membership(self):
        second = Company.objects.create(name="Second", slug="second")
        foreign = Membership.objects.create(
            user=self.bot, company=second, role="developer"
        )
        response = self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": foreign.pk,
                "daily_rate": "9999.00",
                "currency": "INR",
                "effective_from": "2026-01-01",
                "is_on_payroll": "on",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PayrollProfile.objects.filter(user=self.bot).exists())


class PayrollSeedTest(TestCase):
    """The seeder must produce payroll data the calculator accepts."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command("seed_data", "--reset", verbosity=0)

    def test_holidays_and_rates_are_seeded(self):
        self.assertTrue(Holiday.objects.exists())
        self.assertTrue(PayrollProfile.objects.exists())

    def test_every_seeded_rate_is_resolvable_for_the_current_cycle(self):
        start, end = service.cycle_bounds(date.today())
        for company in Company.objects.all():
            for profile in service.payable_people(company, start):
                self.assertGreaterEqual(profile.daily_rate, Decimal("0.00"))
                self.assertLessEqual(profile.effective_from, start)

    def test_the_current_cycle_previews_without_error(self):
        start, end = service.cycle_bounds(date.today())
        for company in Company.objects.all():
            working, rows = service.preview(company, start, end)
            self.assertGreater(working, 0)
            for row in rows:
                self.assertLessEqual(row["payable_days"], Decimal(str(working)))
                # Gross is days x rate, less any flat late penalty. This used to
                # assert `gross == payable_days * daily_rate` outright, which
                # only held because nothing could yet deduct cash -- and it
                # failed or passed depending on the hour the seed ran, since
                # the demo punch times were `now - N hours`.
                self.assertEqual(
                    row["gross"],
                    (row["payable_days"] * row["daily_rate"]
                     - row["late_penalty"]).quantize(Decimal("0.01")),
                )


class PayrollSetupPageTest(PayrollTestBase):
    """The setup screen has to be honest about who is paid and what for."""

    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")

    def get(self):
        return self.client.get(reverse("payroll:profiles"))

    def test_counts_split_on_and_off_payroll(self):
        self.profile(self.dev, "1000.00")                      # on
        self.profile(self.bot, "500.00", on_payroll=False)     # off
        # owner has no profile at all -> counted as not on payroll
        ctx = self.get().context
        self.assertEqual(ctx["on_payroll_count"], 1)
        self.assertEqual(ctx["off_payroll_count"], 2)
        self.assertEqual(ctx["never_set_count"], 1)

    def test_cycle_estimate_is_reused_from_the_service(self):
        """The page must not re-derive the maths; it shows what preview() says."""
        self.profile(self.dev, "1000.00")
        start, end = service.cycle_bounds(date.today())
        # Leave has to sit inside the cycle the page is pricing.
        first = next(d for d in service.working_day_list(self.company, start, end)[:2])
        self.leave(self.dev, first, first, self.unpaid)
        _, expected = service.preview(self.company, start, end)
        row = next(r for r in self.get().context["rows"] if r["user"] == self.dev)
        self.assertEqual(row["estimate"]["gross"], expected[0]["gross"])
        self.assertEqual(row["estimate"]["unpaid_leave_days"], Decimal("1.00"))

    def test_projected_total_counts_only_people_on_payroll(self):
        self.profile(self.dev, "1000.00")
        self.profile(self.bot, "5000.00", on_payroll=False)
        start, end = service.cycle_bounds(date.today())
        working, _ = service.preview(self.company, start, end)
        ctx = self.get().context
        self.assertEqual(ctx["working_days"], working)
        self.assertEqual(ctx["cycle_gross"], Decimal(working) * Decimal("1000.00"))

    def test_off_payroll_row_gets_no_estimate(self):
        self.profile(self.dev, "1000.00")
        self.profile(self.bot, "500.00", on_payroll=False)
        rows = {r["user"].username: r for r in self.get().context["rows"]}
        self.assertIsNone(rows["bot"]["estimate"])
        self.assertIsNotNone(rows["dev"]["estimate"])

    def test_editing_a_rate_prefills_its_own_effective_date(self):
        """Otherwise saving a correction silently opens a new rate row."""
        self.profile(self.dev, "1000.00", effective_from=date(2026, 3, 1))
        row = next(r for r in self.get().context["rows"] if r["user"] == self.dev)
        self.assertEqual(row["form"].initial["effective_from"], date(2026, 3, 1))

    def test_saving_the_prefilled_date_edits_in_place(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 3, 1))
        membership = Membership.objects.get(user=self.dev, company=self.company)
        self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": membership.pk,
                "daily_rate": "1750.00",
                "currency": "INR",
                "effective_from": "2026-03-01",
                "is_on_payroll": "on",
            },
        )
        self.assertEqual(PayrollProfile.objects.filter(user=self.dev).count(), 1)
        self.assertEqual(
            PayrollProfile.objects.get(user=self.dev).daily_rate, Decimal("1750.00")
        )

    def test_a_raise_needs_a_new_effective_date(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 3, 1))
        membership = Membership.objects.get(user=self.dev, company=self.company)
        self.client.post(
            reverse("payroll:profiles"),
            {
                "membership": membership.pk,
                "daily_rate": "1750.00",
                "currency": "INR",
                "effective_from": "2026-11-01",
                "is_on_payroll": "on",
            },
        )
        self.assertEqual(PayrollProfile.objects.filter(user=self.dev).count(), 2)
        # And the new rate is the one that applies from the 1st.
        active = service.active_profile(self.company, self.dev, date(2026, 11, 5))
        self.assertEqual(active.daily_rate, Decimal("1750.00"))

    def test_page_renders_inputs_for_every_member(self):
        for user in (self.dev, self.bot, self.owner):
            self.assertContains(self.get(), f'name="membership"')
        body = self.get().content.decode()
        for user in (self.dev, self.bot, self.owner):
            membership = Membership.objects.get(user=user, company=self.company)
            self.assertIn(f'value="{membership.pk}"', body)

    def test_controls_are_labelled_for_the_person_they_belong_to(self):
        self.assertContains(self.get(), 'aria-label="dev monthly salary"')
        self.assertContains(self.get(), 'aria-label="dev on payroll"')

    def test_history_count_is_surfaced(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 1, 1))
        self.profile(self.dev, "1500.00", effective_from=date(2026, 6, 1))
        self.assertContains(self.get(), "2 rates on record")


class MonthlySalaryTest(PayrollTestBase):
    """A monthly salary is the normal input; the day rate is derived."""

    def monthly(self, user, amount, company=None, effective_from=None):
        return PayrollProfile.objects.create(
            company=company or self.company,
            user=user,
            monthly_salary=Decimal(amount),
            is_on_payroll=True,
            effective_from=effective_from or date(2026, 1, 1),
        )

    def test_daily_rate_is_salary_over_the_cycle_working_days(self):
        """23 working days, so a 24,000 salary is 1043.48/day."""
        self.monthly(self.dev, "24000.00")
        start, end = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(service.working_days(self.company, start, end), 23)
        self.assertEqual(
            service.effective_rate(self.company, PayrollProfile.objects.get(), start),
            Decimal("1043.48"),
        )

    def test_a_full_cycle_pays_the_salary_exactly(self):
        self.monthly(self.dev, "24000.00")
        working, rows = service.preview(self.company, self.start, self.end)
        # 1043.48 x 23 = 24,000.04, i.e. the salary to the nearest paisa.
        self.assertEqual(rows[0]["gross"], Decimal("24000.04"))
        self.assertLessEqual(
            rows[0]["gross"] - Decimal("24000.00"), Decimal("0.05")
        )

    def test_a_holiday_shortens_the_cycle_and_raises_the_day_rate(self):
        """The point: pay does not silently shrink because of a holiday."""
        self.monthly(self.dev, "24000.00")
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        working, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(working, 22)
        self.assertEqual(rows[0]["daily_rate"], Decimal("1090.91"))
        self.assertEqual(rows[0]["gross"], Decimal("24000.02"))

    def test_unpaid_leave_costs_one_divisor_day(self):
        self.monthly(self.dev, "24000.00")
        self.leave(self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid)
        _, rows = service.preview(self.company, self.start, self.end)
        # One day's worth of the derived rate, not a fixed 1/26th.
        self.assertEqual(rows[0]["deduction"], Decimal("3130.44"))
        self.assertEqual(rows[0]["payable_days"], Decimal("20.00"))

    def test_every_person_gets_the_same_salary_for_a_different_day_count(self):
        """A fixed divisor would pay one of these short; there is only one rule."""
        self.monthly(self.dev, "26000.00")
        Holiday.objects.create(
            company=self.company, date=date(2026, 11, 2), name="Diwali"
        )
        working, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(working, 22)               # the cycle still loses the day
        self.assertEqual(rows[0]["daily_rate"], Decimal("1181.82"))
        self.assertEqual(rows[0]["gross"], Decimal("26000.04"))

    def test_a_profile_without_a_salary_uses_its_daily_rate(self):
        self.profile(self.dev, "1200.00")
        start, _ = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(
            service.effective_rate(self.company, PayrollProfile.objects.get(), start),
            Decimal("1200.00"),
        )

    def test_daily_rate_profiles_still_work_end_to_end(self):
        self.profile(self.dev, "1000.00")
        working, rows = service.preview(self.company, self.start, self.end)
        self.assertEqual(rows[0]["gross"], Decimal("23000.00"))

    def test_payslip_records_how_the_rate_was_derived(self):
        self.monthly(self.dev, "24000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        breakdown = run.payslips.get().breakdown
        self.assertEqual(breakdown["monthly_salary"], "24000.00")
        self.assertEqual(breakdown["daily_rate"], "1043.48")
        self.assertEqual(breakdown["working_days"], 23)

    def test_a_daily_rate_payslip_says_so(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        breakdown = run.payslips.get().breakdown
        self.assertNotIn("monthly_salary", breakdown)
        self.assertEqual(breakdown["daily_rate"], "1000.00")

    def test_the_rate_in_force_on_the_cycle_start_prices_the_whole_cycle(self):
        """A raise dated mid-cycle waits for the next one; no half-rate proration."""
        self.monthly(self.dev, "24000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(run.payslips.get().gross, Decimal("24000.04"))

        # Effective 1 Nov, inside the 27 Oct - 26 Nov cycle, so this cycle is
        # still priced at 24,000 ...
        self.monthly(self.dev, "30000.00", effective_from=date(2026, 11, 1))
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(run.payslips.get().gross, Decimal("24000.04"))

        # ... and the next cycle, which starts on the 27th, gets the raise.
        next_start, next_end = service.shift_cycle(self.start, 1)
        run, _ = service.generate_run(self.company, next_start, next_end)
        self.assertEqual(
            run.payslips.get().breakdown["monthly_salary"], "30000.00"
        )

    def test_zero_working_days_pays_nothing_rather_than_dividing_by_zero(self):
        self.monthly(self.dev, "24000.00")
        profile = PayrollProfile.objects.get()
        self.assertEqual(
            service.effective_rate(self.company, profile, self.start), Decimal("1043.48")
        )
        empty = Company.objects.create(name="Shut", slug="shut")
        for day in (date(2026, 10, 27) + timedelta(days=i) for i in range(31)):
            Holiday.objects.create(company=empty, date=day, name="Closed")
        self.assertEqual(service.working_days(empty, self.start, self.end), 0)
        moved = PayrollProfile.objects.get()
        moved.company = empty
        moved.save()
        self.assertEqual(
            service.effective_rate(empty, moved, self.start), Decimal("0.00")
        )


class SalaryFormTest(PayrollTestBase):
    def post(self, **extra):
        membership = Membership.objects.get(user=self.dev, company=self.company)
        data = {
            "membership": membership.pk,
            "currency": "INR",
            "effective_from": "2026-01-01",
            "is_on_payroll": "on",
        }
        data.update(extra)
        return self.client.post(reverse("payroll:profiles"), data)

    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")

    def test_monthly_salary_is_saved_and_no_daily_rate_is_stored(self):
        self.post(monthly_salary="24000")
        profile = PayrollProfile.objects.get()
        self.assertEqual(profile.monthly_salary, Decimal("24000.00"))
        self.assertEqual(profile.daily_rate, Decimal("0.00"))

    def test_a_stale_daily_rate_cannot_take_over_a_monthly_salary(self):
        """A salary wins, so a leftover value in the other box is ignored."""
        self.post(monthly_salary="24000", daily_rate="9999")
        profile = PayrollProfile.objects.get()
        self.assertEqual(profile.monthly_salary, Decimal("24000.00"))
        self.assertEqual(profile.daily_rate, Decimal("0.00"))
        start, _ = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(
            service.effective_rate(self.company, profile, start), Decimal("1043.48")
        )

    def test_a_salary_is_required(self):
        self.post(monthly_salary="", daily_rate="")
        self.assertFalse(PayrollProfile.objects.exists())

    def test_a_daily_rate_still_works_on_its_own(self):
        """The per-day path stays, for anyone not paid a monthly salary."""
        self.post(daily_rate="1200")
        profile = PayrollProfile.objects.get()
        self.assertEqual(profile.daily_rate, Decimal("1200.00"))
        self.assertIsNone(profile.monthly_salary)
        start, _ = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(
            service.effective_rate(self.company, profile, start), Decimal("1200.00")
        )

    def test_a_nonsense_salary_is_rejected(self):
        self.post(monthly_salary="-5")
        self.assertFalse(PayrollProfile.objects.exists())


class SalaryScreenTest(PayrollTestBase):
    """The screen must work with the rendered HTML, not just via the service."""

    def setUp(self):
        super().setUp()
        self.client.login(username="owner", password="pass1234")
        self.membership = Membership.objects.get(user=self.dev, company=self.company)

    def html(self):
        return self.client.get(reverse("payroll:profiles")).content.decode()

    def post_row(self, **fields):
        # Deliberately the browser's payload: no currency unless the row sent one.
        data = {
            "membership": self.membership.pk,
            "effective_from": "2026-01-01",
            "is_on_payroll": "on",
        }
        data.update(fields)
        return self.client.post(reverse("payroll:profiles"), data)

    def test_only_a_salary_box_is_asked_for(self):
        """One concept: the screen must not offer the removed bases."""
        body = self.html()
        self.assertIn('name="monthly_salary"', body)
        self.assertNotIn('name="daily_rate"', body)
        self.assertNotIn('name="salary_basis"', body)
        self.assertNotIn('name="fixed_divisor"', body)
        self.assertNotIn('type="radio"', body)

    def test_the_saved_salary_is_prefilled_without_javascript(self):
        """Alpine's x-model sets the box on boot, but the server renders it too,
        so a disabled-JS browser still shows and posts the current salary."""
        self.monthly_profile(monthly="24000")
        self.assertRegex(
            self.html(),
            r'name="monthly_salary"\s+value="24000\.00"',
        )

    def test_the_derived_rate_hint_shows_the_division(self):
        body = self.html()
        self.assertIn("÷", body)
        # 21 working days in the seeded cycle, not 26 or 30.
        self.assertRegex(body, r"days: 21")

    def test_a_monthly_salary_survives_a_save_through_the_screen(self):
        self.post_row(monthly_salary="24000")
        profile = PayrollProfile.objects.get()
        self.assertEqual(profile.monthly_salary, Decimal("24000.00"))
        self.assertEqual(profile.currency, "INR")
        self.assertTrue(profile.is_on_payroll)
        start, end = service.cycle_bounds(date(2026, 10, 27))
        _, rows = service.preview(self.company, start, end)
        self.assertEqual(rows[0]["gross"], Decimal("24000.04"))

    def test_the_screen_post_works_without_a_currency(self):
        """What the row actually sends: the currency box is not the only field
        the form needs, and a missing one must not silently reject the save."""
        self.post_row(monthly_salary="24000", currency="")
        self.assertEqual(
            PayrollProfile.objects.get().monthly_salary, Decimal("24000.00")
        )

    def test_editing_a_salary_replaces_it_rather_than_adding_a_row(self):
        self.post_row(monthly_salary="24000")
        self.post_row(monthly_salary="26000")
        self.assertEqual(PayrollProfile.objects.count(), 1)
        self.assertEqual(
            PayrollProfile.objects.get().monthly_salary, Decimal("26000.00")
        )

    def monthly_profile(self, monthly=None, rate=None):
        return PayrollProfile.objects.create(
            company=self.company,
            user=self.dev,
            monthly_salary=Decimal(monthly) if monthly else None,
            daily_rate=Decimal(rate) if rate else Decimal("0.00"),
            is_on_payroll=True,
            effective_from=date(2026, 1, 1),
        )


class MyPayslipAccessTest(PayrollTestBase):
    """An employee must be able to see their own payslip, and only their own."""

    def get(self, url):
        return self.client.get(url)

    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1200.00")
        # A colleague in the same company, and a payslip in another company.
        self.colleague = make_user("colleague", self.company)
        self.profile(self.colleague, "9999.00")
        self.outsider = make_user("outsider", self.other)
        self.profile(self.outsider, "5000.00", company=self.other)
        # One generate per (company, cycle). A second call for the same cycle
        # does `run.payslips.all().delete()` and recreates them, so any pk
        # captured before it points at a row that no longer exists.
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.mine = self.run.payslips.get(user=self.dev)
        self.theirs = self.run.payslips.get(user=self.colleague)
        self.foreign_run, _ = service.generate_run(self.other, self.start, self.end)
        self.foreign = self.foreign_run.payslips.get(user=self.outsider)

    def test_a_employee_can_open_their_own_payslips(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(self.get(reverse("payroll:my_payslips")).status_code, 200)
        self.assertEqual(
            self.get(reverse("payroll:my_payslip", args=[self.mine.pk])).status_code,
            200,
        )

    def test_the_list_shows_only_my_own_payslip(self):
        self.client.login(username="dev", password="pass1234")
        response = self.get(reverse("payroll:my_payslips"))
        self.assertContains(response, "1200.00")
        # The colleague is on 9999/day; that figure must not appear at all.
        self.assertNotContains(response, "9999.00")
        self.assertNotContains(response, self.colleague.username)

    def test_my_payslip_detail_shows_my_numbers(self):
        self.client.login(username="dev", password="pass1234")
        response = self.get(reverse("payroll:my_payslip", args=[self.mine.pk]))
        self.assertContains(response, "1200.00")
        self.assertNotContains(response, "9999.00")

    def test_a_colleagues_payslip_is_404_not_403(self):
        """404 rather than 403 on purpose: a 403 would confirm it exists."""
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(
            self.get(reverse("payroll:my_payslip", args=[self.theirs.pk])).status_code,
            404,
        )

    def test_another_companys_payslip_is_404(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(
            self.get(reverse("payroll:my_payslip", args=[self.foreign.pk])).status_code,
            404,
        )

    def test_the_admin_payslip_route_still_refuses_an_employee(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(
            self.get(reverse("payroll:payslip", args=[self.mine.pk])).status_code, 403
        )
        self.assertEqual(self.get(reverse("payroll:run_list")).status_code, 403)
        self.assertEqual(self.get(reverse("payroll:profiles")).status_code, 403)

    def test_an_admin_can_also_reach_the_my_pages(self):
        self.client.login(username="owner", password="pass1234")
        self.assertEqual(self.get(reverse("payroll:my_payslips")).status_code, 200)

    def test_a_viewer_role_member_can_see_their_own(self):
        """is_on_payroll is an admin switch, not a read permission."""
        self.client.login(username="bot", password="pass1234")
        self.assertEqual(self.get(reverse("payroll:my_payslips")).status_code, 200)

    def test_logged_out_is_redirected_to_login(self):
        response = self.get(reverse("payroll:my_payslips"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_not_on_payroll_says_so_instead_of_looking_broken(self):
        self.profile(self.bot, "0.00", on_payroll=False)
        self.client.login(username="bot", password="pass1234")
        self.assertContains(
            self.get(reverse("payroll:my_payslips")), "You are not on payroll"
        )

    def test_the_sidebar_offers_my_payslips_to_an_employee(self):
        self.client.login(username="dev", password="pass1234")
        response = self.get(reverse("leave:my_leave"))
        self.assertContains(response, reverse("payroll:my_payslips"))
        # ...but not the admin-only setup pages.
        self.assertNotContains(response, reverse("payroll:profiles"))


class LatenessDeductionTest(PayrollTestBase):
    """Lateness takes money off the payslip, and the slip says why.

    Two different mechanisms, deliberately not conflated:
      * the Rs 50 / Rs 100 bands are a flat charge subtracted from gross;
      * arriving over an hour late costs half a day, so it is a *day* the
        person is not paid for, exactly like unpaid leave.
    """

    def punch(self, user, day, at):
        from datetime import datetime as _dt
        from datetime import time as _t

        from django.utils import timezone

        from apps.attendance.models import AttendanceRecord

        return AttendanceRecord.objects.create(
            company=self.company,
            user=user,
            date=day,
            check_in=timezone.make_aware(_dt.combine(day, at)),
            check_out=timezone.make_aware(_dt.combine(day, _t(19, 0))),
        )

    def row_for(self, user):
        _days, rows = service.preview(self.company, self.start, self.end)
        return next(r for r in rows if r["user"] == user)

    def test_a_clean_cycle_is_untouched(self):
        """A new penalty must not move the numbers for anyone who is on time."""
        self.profile(self.dev)
        self.punch(self.dev, date(2026, 11, 2), time(9, 30))
        row = self.row_for(self.dev)
        self.assertEqual(row["late_penalty"], Decimal("0.00"))
        self.assertEqual(row["late_half_days"], Decimal("0"))
        self.assertEqual(row["breakdown"]["late_events"], [])
        self.assertEqual(row["gross"], row["payable_days"] * row["daily_rate"])

    def test_a_run_of_lateness_never_quotes_a_negative_gross(self):
        """Deductions cannot exceed earnings.

        `payable_days` was already floored at zero, but the flat cash charge is
        subtracted *after* that floor. On a low salary, being Rs 100 late every
        single day of the cycle cost more than the whole month, and the payslip
        came out at **-99.96** -- a payslip telling the employee to hand money
        back. Cap the charge at what the payable days can absorb, floor gross at
        zero, and keep the uncapped figure in the breakdown so the cap is
        auditable rather than quietly eating the difference.
        """
        profile = self.profile(self.dev, rate="95.24")
        self.start = date(2026, 11, 2)
        self.end = date(2026, 11, 30)
        day = self.start
        while day <= self.end:
            if day.weekday() < 5:
                self.punch(self.dev, day, time(10, 45))  # Rs 100, every day
            day += timedelta(days=1)

        row = self.row_for(self.dev)
        self.assertGreater(row["late_penalty"], Decimal("0"))
        self.assertGreaterEqual(row["gross"], Decimal("0.00"))
        self.assertEqual(row["gross"], Decimal("0.00"))
        # The money is not vanished: it is recorded as uncapped.
        self.assertIn("late_penalty_uncapped", row["breakdown"])
        self.assertNotEqual(
            row["breakdown"]["late_penalty_uncapped"],
            row["breakdown"]["late_penalty"],
        )

    def test_the_cap_does_not_touch_a_normal_payslip(self):
        """The cap is an extreme case only; ordinary numbers must not move."""
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))  # Rs 50
        row = self.row_for(self.dev)
        self.assertEqual(row["late_penalty"], Decimal("50.00"))
        self.assertNotIn("late_penalty_uncapped", row["breakdown"])
        self.assertGreater(row["gross"], Decimal("0.00"))

    def test_cash_bands_are_subtracted_from_gross(self):
        profile = self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))  # Rs 50
        self.punch(self.dev, date(2026, 11, 3), time(10, 45))  # Rs 100
        row = self.row_for(self.dev)
        self.assertEqual(row["late_penalty"], Decimal("150.00"))
        # Days are unaffected; only the cash comes off the top.
        self.assertEqual(
            row["gross"],
            (row["payable_days"] * Decimal("1000.00") - Decimal("150.00")).quantize(
                Decimal("0.01")
            ),
        )
        self.assertEqual(row["breakdown"]["late_penalty"], "INR 150")

    def test_a_half_day_arrival_costs_half_a_days_pay(self):
        self.profile(self.dev, rate="1000.00")
        baseline = self.row_for(self.dev)
        self.punch(self.dev, date(2026, 11, 2), time(11, 30))
        row = self.row_for(self.dev)
        self.assertEqual(row["late_half_days"], Decimal("1"))
        # One day stops being payable...
        self.assertEqual(
            row["payable_days"], baseline["payable_days"] - Decimal("1")
        )
        # ...and is reported as the loss, not folded in invisibly.
        self.assertEqual(row["breakdown"]["late_half_day_loss"], "INR 500")
        self.assertEqual(row["breakdown"]["late_half_days"], "1")
        self.assertEqual(
            row["gross"],
            (row["payable_days"] * Decimal("1000.00")).quantize(Decimal("0.01")),
        )

    def test_a_half_day_also_shows_up_in_the_deduction_total(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))  # 50 cash
        self.punch(self.dev, date(2026, 11, 3), time(11, 30))  # half day
        row = self.row_for(self.dev)
        self.assertEqual(row["deduction"], Decimal("550.00"))

    def test_the_payslip_carries_every_event_with_a_reason(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))
        self.punch(self.dev, date(2026, 11, 3), time(11, 30))
        run, created = service.generate_run(self.company, self.start, self.end)
        slip = run.payslips.get(user=self.dev)
        self.assertEqual(slip.late_penalty, Decimal("50.00"))
        self.assertEqual(slip.late_half_days, Decimal("1"))
        events = slip.breakdown["late_events"]
        self.assertEqual(
            [e["date"] for e in events], ["2026-11-02", "2026-11-03"]
        )
        for event in events:
            with self.subTest(date=event["date"]):
                self.assertIn(event["date"], event["reason"])
                self.assertIn("shift start", event["reason"])

    def test_lateness_and_half_a_day_combine(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))
        self.punch(self.dev, date(2026, 11, 3), time(10, 45))
        self.punch(self.dev, date(2026, 11, 4), time(11, 30))
        row = self.row_for(self.dev)
        self.assertEqual(row["late_penalty"], Decimal("150.00"))
        self.assertEqual(row["late_half_days"], Decimal("1"))

    def test_another_person_is_not_charged_for_someone_elses_lateness(self):
        self.profile(self.dev, rate="1000.00")
        self.profile(self.owner, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(11, 30))
        self.assertEqual(self.row_for(self.owner)["late_half_days"], Decimal("0"))

    def test_a_late_day_outside_the_cycle_is_ignored(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 10, 26), time(11, 30))  # day before start
        self.punch(self.dev, date(2026, 11, 27), time(11, 30))  # day after end
        self.assertEqual(self.row_for(self.dev)["late_half_days"], Decimal("0"))

    def test_a_missing_punch_is_never_a_penalty(self):
        self.profile(self.dev, rate="1000.00")
        from apps.attendance.models import AttendanceRecord

        AttendanceRecord.objects.create(
            company=self.company, user=self.dev, date=date(2026, 11, 2)
        )
        self.assertEqual(self.row_for(self.dev)["late_penalty"], Decimal("0.00"))

    def test_editing_a_punch_moves_the_numbers_on_a_refreshed_run(self):
        """Penalties are derived, so fixing attendance and re-running is enough."""
        from apps.attendance.models import AttendanceRecord

        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(11, 30))
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(run.payslips.get(user=self.dev).late_half_days, Decimal("1"))

        # An admin correcting the punch edits the same row.
        from datetime import datetime as _dt

        from django.utils import timezone

        record = AttendanceRecord.objects.get(
            company=self.company, user=self.dev, date=date(2026, 11, 2)
        )
        record.check_in = timezone.make_aware(_dt.combine(date(2026, 11, 2), time(9, 30)))
        record.save(update_fields=["check_in"])
        service.generate_run(self.company, self.start, self.end)
        run.refresh_from_db()
        self.assertEqual(
            run.payslips.get(user=self.dev).late_half_days, Decimal("0")
        )

    def test_a_locked_run_is_never_rewritten_by_a_later_arrival(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, date(2026, 11, 2), time(10, 20))
        run, _ = service.generate_run(self.company, self.start, self.end)
        run.is_locked = True
        run.save()

        self.punch(self.dev, date(2026, 11, 3), time(11, 30))
        again, created = service.generate_run(self.company, self.start, self.end)
        self.assertFalse(created)
        self.assertEqual(
            again.payslips.get(user=self.dev).late_penalty, Decimal("50.00")
        )


class LatenessOnScreenTest(PayrollTestBase):
    """The deduction is only fair if the person can see why it happened.

    Both the admin's copy of the slip and the employee's own must name the
    date, the band and the cost -- a silent deduction from someone's salary is
    a bug, not a feature.
    """

    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1000.00")
        from datetime import datetime as _dt

        from django.utils import timezone

        from apps.attendance.models import AttendanceRecord

        for day, at in ((date(2026, 11, 2), time(10, 20)), (date(2026, 11, 3), time(11, 30))):
            AttendanceRecord.objects.create(
                company=self.company,
                user=self.dev,
                date=day,
                check_in=timezone.make_aware(_dt.combine(day, at)),
                check_out=timezone.make_aware(_dt.combine(day, time(19, 0))),
            )
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.slip = self.run.payslips.get(user=self.dev)

    def as_admin(self):
        self.client.force_login(self.owner)
        return self.client.get(
            reverse("payroll:payslip", args=[self.slip.pk])
        )

    def as_employee(self):
        self.client.force_login(self.dev)
        return self.client.get(
            reverse("payroll:my_payslip", args=[self.slip.pk])
        )

    def test_the_admin_payslip_lists_every_late_day_and_what_it_cost(self):
        html = self.as_admin().content.decode()
        self.assertContains(self.as_admin(), "Late arrivals")
        # Date, the lateness, and the money for each of the two events.
        self.assertIn("2026-11-02", html)
        self.assertIn("20 min after", html)
        self.assertIn("2026-11-03", html)
        self.assertIn("half day", html)
        self.assertIn("50.00", html)

    def test_the_employee_sees_the_same_explanation(self):
        response = self.as_employee()
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Your late arrivals", html)
        self.assertIn("2026-11-02", html)
        self.assertIn("20 min after", html)
        self.assertIn("half day", html)

    def test_the_deduction_total_reaches_the_page(self):
        self.assertContains(self.as_admin(), "50.00")  # Rs 50 band

    def test_an_on_time_payslip_has_no_late_section_at_all(self):
        """No charge means no scary heading: absence is the correct display."""
        clean = make_user("clean", self.company)
        self.profile(clean, "1000.00")
        service.generate_run(self.company, self.start, self.end)
        slip = self.run.payslips.get(user=clean)
        self.client.force_login(self.owner)
        html = self.client.get(
            reverse("payroll:payslip", args=[slip.pk])
        ).content.decode()
        self.assertNotIn("Late arrivals", html)

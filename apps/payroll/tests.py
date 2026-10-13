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

    def leave(self, user, start, end, policy, status="approved", half=False,
              paid=None, unpaid=None):
        """A leave request, split stored the way an application or an approval
        stores it.
        """
        days = Decimal("0.5") if half else Decimal(
            str(len(service._weekdays(start, end)))
        )
        if paid is None and unpaid is None:
            pd = days if policy.is_paid else Decimal("0")
            ud = Decimal("0") if policy.is_paid else days
            sm = "auto"
        else:
            pd = paid if paid is not None else days - unpaid
            ud = unpaid if unpaid is not None else days - paid
            sm = "manual"
        return LeaveRequest.objects.create(
            company=self.company,
            user=user,
            policy=policy,
            start_date=start,
            end_date=end,
            is_half_day=half,
            days=days,
            paid_days=pd,
            unpaid_days=ud,
            split_mode=sm,
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

    def test_the_stored_split_wins_over_the_policy(self):
        """An approver can mark a paid type's days unpaid, and payroll must agree.

        This is the case the split was added for: a developer is marked
        unpaid-only for a launch week under a Casual policy that is normally
        paid in full. Reading the policy instead of the request would pay them.
        """
        self.leave(
            self.dev, date(2026, 11, 2), date(2026, 11, 4), self.casual,
            paid=Decimal("1"), unpaid=Decimal("2"),
        )
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["paid_days"], Decimal("1.00"))
        self.assertEqual(result["unpaid_days"], Decimal("2.00"))

    def test_an_approver_can_mark_an_unpaid_types_days_paid(self):
        """An override in the paid direction is honoured, not second-guessed.

        `is_paid=False` is the default for that type, not a floor on what may be
        approved: "pay this one, he's covering the release" is a real decision
        and the approver is the only person who can make it. Payroll reads the
        stored split, so the exception survives into the payslip.
        """
        self.leave(
            self.dev, date(2026, 11, 2), date(2026, 11, 4), self.unpaid,
            paid=Decimal("3"), unpaid=Decimal("0"),
        )
        result = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        self.assertEqual(result["paid_days"], Decimal("3.00"))
        self.assertEqual(result["unpaid_days"], Decimal("0.00"))

    def test_a_part_unpaid_spell_is_billed_paid_days_first(self):
        """Paid days come from the start of the span, as `auto_split` decided.

        The straddle case is where the two halves have to agree: 3 paid + 2
        unpaid over a span crossing the 27th must cost the same total whichever
        cycle is run. Charging unpaid first would move a paid day into the later
        cycle and change the per-cycle figures the payslips quote.
        """
        self.leave(
            self.dev, date(2026, 10, 23), date(2026, 11, 4), self.casual,
            paid=Decimal("3"), unpaid=Decimal("6"),
        )
        first = service.leave_days_in_period(
            self.company, self.dev, date(2026, 9, 27), date(2026, 10, 26)
        )
        second = service.leave_days_in_period(
            self.company, self.dev, self.start, self.end
        )
        # 23, 26 Oct fall in the first cycle: both are within the 3 paid days,
        # so the whole first cycle is paid.
        self.assertEqual(first["paid_days"], Decimal("2.00"))
        self.assertEqual(first["unpaid_days"], Decimal("0.00"))
        # The third paid day lands on 27 Oct; everything after it is unpaid.
        self.assertEqual(second["paid_days"], Decimal("1.00"))
        self.assertEqual(second["unpaid_days"], Decimal("6.00"))
        # Nothing is lost or invented across the boundary.
        self.assertEqual(
            first["paid_days"] + second["paid_days"], Decimal("3.00")
        )
        self.assertEqual(
            first["unpaid_days"] + second["unpaid_days"], Decimal("6.00")
        )

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


class RunIntegrityAndAuditTest(PayrollTestBase):
    def test_a_failure_while_writing_payslips_leaves_the_old_ones_intact(self):
        from unittest import mock

        self.profile(self.dev)
        self.profile(self.bot)
        run, _ = service.generate_run(self.company, self.start, self.end)
        before = list(run.payslips.values_list("pk", flat=True))
        self.assertEqual(len(before), 2)

        real_create = Payslip.objects.create
        calls = {"n": 0}

        def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("disk full")
            return real_create(*args, **kwargs)

        with mock.patch.object(Payslip.objects, "create", side_effect=flaky):
            with self.assertRaises(RuntimeError):
                service.generate_run(self.company, self.start, self.end)
        self.assertEqual(list(run.payslips.values_list("pk", flat=True)), before)

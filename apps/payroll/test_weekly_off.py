"""Payroll counts working days from the company's weekly offs, and never prices work done on one."""
from datetime import date, datetime, time
from decimal import Decimal

from django.utils import timezone

from apps.attendance import service as attendance
from apps.attendance.models import AttendanceRecord
from apps.leave.models import LeaveRequest
from apps.payroll import service
from apps.payroll.models import PayrollProfile
from apps.payroll.tests import PayrollTestBase

# The cycle is 27 Oct - 26 Nov 2026: 23 weekdays, 4 Saturdays (31 Oct is the first), 4 Sundays.
SATURDAY, MONDAY = date(2026, 10, 31), date(2026, 11, 2)


class WeeklyOffPayrollTest(PayrollTestBase):
    def set_off(self, *days):
        attendance.set_weekly_off(self.company, [str(d) for d in days])

    def punch(self, user, day, at):
        tz = timezone.get_current_timezone()
        return AttendanceRecord.objects.create(
            company=self.company, user=user, date=day,
            check_in=timezone.make_aware(datetime.combine(day, at), tz),
            check_out=timezone.make_aware(datetime.combine(day, time(19, 0)), tz),
        )

    def row_for(self, user):
        _days, rows = service.preview(self.company, self.start, self.end)
        return next(r for r in rows if r["user"] == user)

    def test_working_days_are_the_cycle_less_the_companys_weekly_offs(self):
        count = lambda: service.working_days(self.company, self.start, self.end)
        self.assertEqual(count(), 23)
        self.set_off(6)  # Saturdays work now
        self.assertEqual(count(), 27)
        self.assertEqual(len(service.working_day_list(self.company, self.start, self.end)), 27)
        self.set_off(5, 6, 0)  # Mondays are off too: 4 of them in the cycle
        self.assertEqual(count(), 19)
        self.set_off()
        self.assertEqual(count(), 31)

    def test_a_monthly_salary_is_still_paid_in_full_with_other_offs(self):
        """The divisor moves with the calendar, so the whole salary is paid either way."""
        profile = PayrollProfile.objects.create(
            company=self.company, user=self.dev, monthly_salary=Decimal("27000.00"),
            is_on_payroll=True, effective_from=date(2026, 1, 1),
        )
        self.assertEqual(service.effective_rate(self.company, profile, self.start), Decimal("1173.91"))
        self.set_off(6)
        self.assertEqual(service.effective_rate(self.company, profile, self.start), Decimal("1000.00"))
        self.assertEqual(self.row_for(self.dev)["gross"], Decimal("27000.00"))

    def test_a_late_saturday_costs_nothing_but_a_late_monday_does(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, SATURDAY, time(11, 30))
        row = self.row_for(self.dev)
        self.assertEqual((row["late_penalty"], row["late_half_days"]), (Decimal("0.00"), Decimal("0")))
        self.assertEqual(row["breakdown"]["late_events"], [])
        self.assertEqual(row["gross"], row["payable_days"] * row["daily_rate"])

        self.punch(self.dev, MONDAY, time(11, 30))
        self.assertEqual(self.row_for(self.dev)["late_half_days"], Decimal("1"))

    def test_changing_the_off_days_moves_the_deduction(self):
        self.profile(self.dev, rate="1000.00")
        self.punch(self.dev, SATURDAY, time(11, 30))
        self.assertEqual(self.row_for(self.dev)["late_half_days"], Decimal("0"))
        self.set_off(6)  # Saturday is a working day now, so 11:30 is a half day
        self.assertEqual(self.row_for(self.dev)["late_half_days"], Decimal("1"))

    def test_work_on_an_off_day_adds_and_takes_nothing(self):
        self.profile(self.dev, rate="1000.00")
        before = self.row_for(self.dev)
        self.punch(self.dev, SATURDAY, time(9, 0))
        self.punch(self.dev, date(2026, 11, 1), time(23, 0))  # a Sunday night
        after = self.row_for(self.dev)
        for key in ("working_days", "payable_days", "gross", "deduction", "late_penalty"):
            self.assertEqual(after[key], before[key], key)

    def test_unpaid_leave_is_charged_on_working_days_only(self):
        self.profile(self.dev, rate="1000.00")
        fri, mon = date(2026, 10, 30), MONDAY
        self.leave(self.dev, fri, mon, self.unpaid)  # Friday and Monday: 2 days
        self.assertEqual(self.row_for(self.dev)["unpaid_leave_days"], Decimal("2"))
        LeaveRequest.objects.all().delete()
        self.set_off(6)  # Saturday works now: Friday, Saturday, Monday
        LeaveRequest.objects.create(
            company=self.company, user=self.dev, policy=self.unpaid, start_date=fri, end_date=mon,
            days=Decimal("3"), paid_days=Decimal("0"), unpaid_days=Decimal("3"),
            split_mode="auto", status="approved",
        )
        self.assertEqual(self.row_for(self.dev)["unpaid_leave_days"], Decimal("3"))

    def test_a_locked_run_ignores_a_new_calendar(self):
        self.profile(self.dev, rate="1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        run.is_locked = True
        run.save()
        slip = run.payslips.get(user=self.dev)

        self.set_off(6)
        again, created = service.generate_run(self.company, self.start, self.end)
        self.assertFalse(created)
        self.assertEqual(again.working_days, 23)
        fresh = again.payslips.get(user=self.dev)
        self.assertEqual((fresh.pk, fresh.working_days, fresh.gross), (slip.pk, 23, slip.gross))

"""An expense marked "to salary" is repaid on the payer's next payslip, once."""
from datetime import date
from decimal import Decimal

from apps.expenses.models import Expense
from apps.payroll import service
from apps.payroll.tests import PayrollTestBase


class ReimbursementTest(PayrollTestBase):
    def expense(self, paise=50000, on=date(2026, 11, 3), **kw):
        return Expense.objects.create(
            company=self.company, amount_paise=paise, date=on,
            paid_by=self.dev, created_by=self.dev, **kw,
        )

    def slip(self):
        return self.dev.payslips.get()

    def test_marked_expense_lands_on_the_slip_once(self):
        self.profile(self.dev, rate="1000.00")
        e = self.expense(to_salary=True)
        plain = self.expense(to_salary=False)
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(self.slip().reimbursement, Decimal("500.00"))
        e.refresh_from_db(); plain.refresh_from_db()
        self.assertEqual((e.paid_in_run, plain.paid_in_run), (run, None))
        base = self.slip().gross - Decimal("500.00")
        # Regenerating an open run keeps it, and does not pay it twice.
        service.generate_run(self.company, self.start, self.end)
        self.assertEqual((self.slip().reimbursement, self.slip().gross), (Decimal("500.00"), base + Decimal("500.00")))
        # The next cycle does not repeat it.
        service.generate_run(self.company, *service.shift_cycle(self.start, 1))
        self.assertEqual(self.dev.payslips.order_by("-run__period_start").first().reimbursement, 0)

    def test_expense_after_the_cycle_waits(self):
        self.profile(self.dev, rate="1000.00")
        self.expense(on=date(2026, 12, 1), to_salary=True)
        service.generate_run(self.company, self.start, self.end)
        self.assertEqual(self.slip().reimbursement, 0)

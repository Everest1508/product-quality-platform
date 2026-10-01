"""Tests for reading, auditing and repairing unreadable DecimalField values.

The failure this covers is not a bug in a view: it is a row that Django's SQLite
decimal converter cannot read, which 500s every page whose query touches the
table -- the dashboard being the one that surfaced it in production.
"""

import json
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.accounts.models import Company, Membership, User
from apps.core import decimals
from apps.payroll.models import PayrollProfile


class DecimalReadTest(TestCase):
    """`decimal_read_error` must agree with the backend's own converter."""

    def test_accepts_an_ordinary_value(self):
        self.assertIsNone(decimals.decimal_read_error(50000.0, 2))

    def test_rejects_infinity(self):
        self.assertIn("non-finite", decimals.decimal_read_error(float("inf"), 2))

    def test_rejects_nan(self):
        self.assertIn("non-finite", decimals.decimal_read_error(float("nan"), 2))

    def test_rejects_a_magnitude_the_context_cannot_quantize(self):
        self.assertIn("quantize", decimals.decimal_read_error(1e30, 2))

    def test_rejects_text_that_is_not_a_number(self):
        # NUMERIC affinity leaves non-numeric text as TEXT, and the backend
        # converter's create_decimal_from_float refuses a str outright.
        self.assertIn("not a number", decimals.decimal_read_error("not-a-number", 2))

    def test_extra_decimal_places_round_rather_than_fail(self):
        # The backend quantizes with the default context (ROUND_HALF_EVEN), so
        # 1.005 in a 1dp column rounds to 1.0. Over-precision is not the failure
        # mode; the form validators own that, and only magnitude is fatal here.
        self.assertIsNone(decimals.decimal_read_error(1.005, 1))


class UnreadableDecimalRowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t", email="t@example.com", password="x"
        )
        self.company = Company.objects.create(name="Acme")
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.OWNER
        )
        self.profile = PayrollProfile.objects.create(
            company=self.company,
            user=self.user,
            monthly_salary=Decimal("50000.00"),
            is_on_payroll=True,
        )

    def _poison(self, value):
        """Write a value the ORM's own converter would reject.

        Raw SQL is the only way in: `Profile.objects.get()` raises before
        returning, which is the whole problem.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?",
                [value, self.profile.pk],
            )

    def test_a_poisoned_row_cannot_be_read_through_the_orm(self):
        self._poison(float("inf"))
        with self.assertRaises(Exception) as ctx:
            PayrollProfile.objects.get(pk=self.profile.pk)
        self.assertIn("InvalidOperation", type(ctx.exception).__name__)

    def test_scan_names_the_row(self):
        self._poison(float("inf"))
        problems = decimals.scan()
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["model"], "payroll.PayrollProfile")
        self.assertEqual(problems[0]["column"], "monthly_salary")
        self.assertEqual(problems[0]["pk"], self.profile.pk)

    def test_scan_can_be_narrowed_to_one_model(self):
        self._poison(float("inf"))
        self.assertEqual(decimals.scan(model_label="payroll.Payslip"), [])
        self.assertEqual(len(decimals.scan(model_label="payroll.PayrollProfile")), 1)

    def test_a_healthy_database_scans_clean(self):
        self.assertEqual(decimals.scan(), [])

    def test_repair_makes_the_row_readable_again(self):
        self._poison(float("inf"))
        changed = decimals.repair(decimals.scan(), replacement=Decimal("0.00"))
        self.assertEqual(len(changed), 1)
        self.assertEqual(
            PayrollProfile.objects.get(pk=self.profile.pk).monthly_salary,
            Decimal("0.00"),
        )

    def test_repair_leaves_healthy_rows_alone(self):
        before = self.profile.monthly_salary
        decimals.repair(decimals.scan(), replacement=Decimal("0.00"))
        self.assertEqual(
            PayrollProfile.objects.get(pk=self.profile.pk).monthly_salary, before
        )


class AuditDecimalsCommandTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="t", email="t@example.com", password="x"
        )
        self.company = Company.objects.create(name="Acme")
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.OWNER
        )
        self.profile = PayrollProfile.objects.create(
            company=self.company,
            user=self.user,
            monthly_salary=Decimal("50000.00"),
            is_on_payroll=True,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payroll_payrollprofile SET monthly_salary = ? WHERE id = ?",
                [float("inf"), self.profile.pk],
            )

    def test_reports_without_writing(self):
        out = self._run()
        self.assertIn("unreadable decimal value", out)
        self.assertIn("monthly_salary", out)
        with self.assertRaises(Exception):
            PayrollProfile.objects.get(pk=self.profile.pk)

    def test_fix_writes_and_says_so(self):
        out = self._run(extra=["--fix", "--set", "0.00"])
        self.assertIn("Repaired 1 cell", out)
        self.assertEqual(
            PayrollProfile.objects.get(pk=self.profile.pk).monthly_salary,
            Decimal("0.00"),
        )

    def test_backup_records_the_raw_value_before_the_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decimals.json"
            self._run(extra=["--fix", "--backup", str(path)])
            payload = json.loads(path.read_text())
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["raw"], "inf")
        self.assertEqual(payload[0]["column"], "monthly_salary")

    def _run(self, extra=None):
        from io import StringIO

        buffer = StringIO()
        call_command("audit_decimals", *(extra or []), stdout=buffer)
        return buffer.getvalue()

from datetime import date, datetime, time
from decimal import Decimal

from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance.models import AttendanceRecord
from apps.dashboards.models import ActivityLog
from apps.payroll import service
from apps.payroll.models import Holiday, Payslip, PayrollProfile, PayrollRun
from apps.payroll.tests import PayrollTestBase, make_user

API = "/ui-api/v1/payroll/"


class P(PayrollTestBase):
    def login(self, name):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.company.pk
        s.save()

    def post(self, path, body=None):
        return self.client.post(API + path, body or {}, content_type="application/json")

    def get(self, path, **q):
        return self.client.get(API + path, q)


class AccessTest(P):
    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1000.00")
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.slip = self.run.payslips.get()

    def admin_paths(self):
        return ["runs/", "preview/", "profiles/", "holidays/", f"runs/{self.run.pk}/", f"payslips/{self.slip.pk}/"]

    def test_admin_opens_everything(self):
        self.login("owner")
        for p in self.admin_paths():
            self.assertEqual(self.get(p).status_code, 200, p)

    def test_developer_is_locked_out_of_every_admin_endpoint_and_write(self):
        self.login("dev")
        for p in self.admin_paths():
            self.assertEqual(self.get(p).status_code, 403, p)
        self.assertEqual(self.post("preview/").status_code, 403)
        self.assertEqual(self.post(f"runs/{self.run.pk}/lock/").status_code, 403)
        self.assertEqual(self.post("holidays/", {"date": "2026-11-02", "name": "x"}).status_code, 403)
        self.assertEqual(self.post("profiles/", {"membership": 1}).status_code, 403)
        self.assertEqual(self.client.delete(API + "holidays/1/").status_code, 403)
        self.assertEqual(PayrollRun.objects.count(), 1)
        self.assertFalse(Holiday.objects.exists())

    def test_anonymous_is_refused(self):
        self.assertIn(Client().get(API + "runs/").status_code, (401, 403))

    def test_another_companys_payslip_and_run_are_404(self):
        other_run = PayrollRun.objects.create(company=self.other, period_start=self.start, period_end=self.end)
        other_slip = Payslip.objects.create(company=self.other, run=other_run, user=self.bot, daily_rate=Decimal("100.00"), gross=Decimal("100.00"))
        self.login("owner")
        self.assertEqual(self.get(f"payslips/{other_slip.pk}/").status_code, 404)
        self.assertEqual(self.get(f"runs/{other_run.pk}/").status_code, 404)
        self.assertEqual(self.post(f"runs/{other_run.pk}/lock/").status_code, 404)

    def test_another_companys_holiday_cannot_be_removed(self):
        holiday = Holiday.objects.create(company=self.other, date=date(2026, 11, 2), name="X")
        self.login("owner")
        self.assertEqual(self.client.delete(API + f"holidays/{holiday.pk}/").status_code, 404)
        self.assertTrue(Holiday.objects.filter(pk=holiday.pk).exists())


class RunsApiTest(P):
    def setUp(self):
        super().setUp()
        self.login("owner")

    def test_preview_shows_the_numbers_for_the_asked_cycle(self):
        self.profile(self.dev, "1000.00")
        d = self.get("preview/", anchor="2026-10-27").json()
        self.assertEqual((d["working_days"], d["start"], d["end"]), (23, "2026-10-27", "2026-11-26"))
        self.assertEqual((d["rows"][0]["gross"], d["total_gross"], d["total_deduction"]), ("23000.00", "23000.00", "0.00"))
        self.assertEqual(d["rows"][0]["person"]["username"], "dev")

    def test_preview_defaults_to_the_cycle_running_today_and_survives_junk(self):
        expected = service.cycle_bounds(date.today())
        d = self.get("preview/").json()
        self.assertEqual((d["start"], d["end"]), tuple(x.isoformat() for x in expected))
        self.assertEqual(self.get("preview/", anchor="garbage").json()["start"], expected[0].isoformat())

    def test_generate_snapshots_and_a_locked_cycle_is_left_alone(self):
        self.profile(self.dev, "1000.00")
        r = self.post("preview/", {"anchor": "2026-10-27"}).json()
        self.assertIn("Payroll generated for", r["message"])
        run = PayrollRun.objects.get()
        self.assertEqual((r["run_id"], Payslip.objects.count()), (run.pk, 1))
        self.assertTrue(ActivityLog.objects.filter(event_type="payroll_run").exists())
        run.is_locked = True
        run.save()
        self.assertIn("is locked and was left unchanged", self.post("preview/", {"anchor": "2026-10-27"}).json()["message"])

    def test_the_list_marks_the_current_cycle_once_it_has_a_run(self):
        self.profile(self.dev, "1000.00")
        d = self.get("runs/").json()
        self.assertEqual((d["runs"], d["has_current_run"]), ([], False))
        self.post("preview/")
        d = self.get("runs/").json()
        self.assertTrue(d["has_current_run"])
        self.assertEqual((d["runs"][0]["payslips"], d["runs"][0]["is_locked"]), (1, False))

    def test_the_detail_has_the_totals_and_every_slip(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        d = self.get(f"runs/{run.pk}/").json()
        self.assertEqual((d["label"], d["total_gross"], d["total_payable"], len(d["slips"])), ("27 Oct 2026 → 26 Nov 2026", "23000.00", "23.00", 1))

    def test_lock_toggles_and_is_logged(self):
        self.profile(self.dev, "1000.00")
        run, _ = service.generate_run(self.company, self.start, self.end)
        self.assertEqual(self.post(f"runs/{run.pk}/lock/").json()["is_locked"], True)
        self.assertEqual(self.post(f"runs/{run.pk}/lock/").json()["is_locked"], False)
        events = list(ActivityLog.objects.filter(company=self.company).values_list("event_type", flat=True))
        self.assertIn("payroll_run_locked", events)
        self.assertIn("payroll_run_unlocked", events)


class HolidayApiTest(P):
    def setUp(self):
        super().setUp()
        self.login("owner")

    def test_add_list_and_remove_with_the_activity_logged(self):
        r = self.post("holidays/", {"date": "2026-11-02", "name": "Diwali"})
        self.assertEqual((r.status_code, r.json()["message"]), (201, "Diwali added."))
        self.assertEqual([h["name"] for h in self.get("holidays/").json()["holidays"]], ["Diwali"])
        h = Holiday.objects.get()
        self.assertIn("removed", self.client.delete(API + f"holidays/{h.pk}/").json()["message"])
        events = ActivityLog.objects.filter(company=self.company).values_list("event_type", flat=True)
        self.assertIn("holiday_added", events)
        self.assertIn("holiday_removed", events)

    def test_a_duplicate_date_is_a_field_error(self):
        Holiday.objects.create(company=self.company, date=date(2026, 11, 2), name="Diwali")
        r = self.post("holidays/", {"date": "2026-11-02", "name": "Again"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("date", r.json()["errors"])
        self.assertEqual(Holiday.objects.count(), 1)

    def test_a_blank_name_and_a_bad_date_are_refused(self):
        r = self.post("holidays/", {"date": "2026-11-03", "name": "  "})
        self.assertEqual((r.status_code, "name" in r.json()["errors"]), (400, True))
        self.assertEqual(self.post("holidays/", {"date": "nope", "name": "x"}).status_code, 400)
        self.assertEqual(self.post("holidays/", []).status_code, 400)


class ProfileApiTest(P):
    def setUp(self):
        super().setUp()
        self.login("owner")
        self.m = Membership.objects.get(user=self.dev, company=self.company)

    def save(self, **extra):
        body = {"membership": self.m.pk, "currency": "INR", "effective_from": "2026-01-01", "is_on_payroll": True, **extra}
        return self.post("profiles/", body)

    def rows(self):
        return {r["person"]["username"]: r for r in self.get("profiles/").json()["rows"]}

    def test_every_member_is_listed_with_their_own_membership_id(self):
        d = self.get("profiles/").json()
        self.assertEqual(len(d["rows"]), 3)
        self.assertEqual(self.rows()["dev"]["membership_id"], self.m.pk)

    def test_a_monthly_salary_is_saved_with_no_daily_rate(self):
        r = self.save(monthly_salary="24000")
        self.assertEqual((r.status_code, r.json()["message"]), (200, "Payroll set for dev."))
        p = PayrollProfile.objects.get()
        self.assertEqual((p.monthly_salary, p.daily_rate, p.currency, p.is_on_payroll), (Decimal("24000.00"), Decimal("0.00"), "INR", True))
        start, end = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(service.preview(self.company, start, end)[1][0]["gross"], Decimal("24000.04"))
        self.assertEqual(r.json()["rows"][0]["person"]["username"] in ("dev", "bot", "owner"), True)

    def test_a_stale_daily_rate_cannot_take_over_a_salary(self):
        self.save(monthly_salary="24000", daily_rate="9999")
        p = PayrollProfile.objects.get()
        self.assertEqual((p.monthly_salary, p.daily_rate), (Decimal("24000.00"), Decimal("0.00")))
        start, _ = service.cycle_bounds(date(2026, 10, 27))
        self.assertEqual(service.effective_rate(self.company, p, start), Decimal("1043.48"))

    def test_a_daily_rate_still_works_alone_and_a_missing_salary_is_refused(self):
        self.assertEqual(self.save(daily_rate="1200").status_code, 200)
        self.assertEqual(PayrollProfile.objects.get().daily_rate, Decimal("1200.00"))
        PayrollProfile.objects.all().delete()
        for bad in ({"monthly_salary": "", "daily_rate": ""}, {"monthly_salary": "-5"}):
            r = self.save(**bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("monthly_salary", r.json()["errors"])
        self.assertFalse(PayrollProfile.objects.exists())

    def test_the_same_date_edits_a_new_date_opens_a_rate_and_a_blank_currency_is_inr(self):
        self.save(monthly_salary="24000", currency="")
        self.save(monthly_salary="26000")
        self.assertEqual((PayrollProfile.objects.count(), PayrollProfile.objects.get().monthly_salary), (1, Decimal("26000.00")))
        self.assertEqual(PayrollProfile.objects.get().currency, "INR")
        self.save(monthly_salary="30000", effective_from="2026-11-01")
        self.assertEqual(PayrollProfile.objects.count(), 2)
        self.assertEqual(service.active_profile(self.company, self.dev, date(2026, 11, 5)).monthly_salary, Decimal("30000.00"))
        d = self.rows()["dev"]
        self.assertEqual((d["rates"], d["monthly_salary"], d["effective_from"]), (2, "30000.00", "2026-11-01"))

    def test_unticking_removes_someone_from_the_next_run_and_the_log_says_per_month(self):
        self.profile(self.dev, "1000.00")
        self.save(daily_rate="1000", is_on_payroll=False)
        self.assertEqual(service.preview(self.company, self.start, self.end)[1], [])
        PayrollProfile.objects.all().delete()
        self.save(monthly_salary="24000")
        entry = ActivityLog.objects.filter(company=self.company, event_type="payroll_profile_saved").first()
        self.assertIn("per month", entry.description)
        self.assertNotIn("0.00 per day", entry.description)

    def test_another_companys_membership_is_404(self):
        second = Company.objects.create(name="Second", slug="second")
        foreign = Membership.objects.create(user=self.bot, company=second, role="developer")
        self.assertEqual(self.save(membership=foreign.pk, daily_rate="9999").status_code, 404)
        self.assertFalse(PayrollProfile.objects.filter(user=self.bot).exists())

    def test_the_counts_the_estimate_and_the_projection_come_from_the_service(self):
        self.profile(self.dev, "1000.00")
        self.profile(self.bot, "5000.00", on_payroll=False)
        start, end = service.cycle_bounds(date.today())
        first = next(iter(service.working_day_list(self.company, start, end)[:2]))
        self.leave(self.dev, first, first, self.unpaid)
        d = self.get("profiles/").json()
        _, expected = service.preview(self.company, start, end)
        self.assertEqual((d["on_payroll"], d["off_payroll"]), (1, 2))
        rows = {r["person"]["username"]: r for r in d["rows"]}
        self.assertEqual(rows["dev"]["estimate"]["gross"], str(expected[0]["gross"]))
        self.assertEqual(rows["dev"]["estimate"]["unpaid_leave_days"], "1.00")
        self.assertIsNone(rows["bot"]["estimate"])
        self.assertEqual(d["cycle_gross"], str(expected[0]["gross"]))
        self.assertFalse(rows["owner"]["has_profile"])

    def test_the_form_prefills_the_current_rates_own_date(self):
        self.profile(self.dev, "1000.00", effective_from=date(2026, 3, 1))
        self.assertEqual(self.rows()["dev"]["effective_from"], "2026-03-01")


class MyPayslipsApiTest(P):
    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1200.00")
        self.colleague = make_user("colleague", self.company)
        self.profile(self.colleague, "9999.00")
        self.outsider = make_user("outsider", self.other)
        self.profile(self.outsider, "5000.00", company=self.other)
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.mine = self.run.payslips.get(user=self.dev)
        self.theirs = self.run.payslips.get(user=self.colleague)
        self.foreign = service.generate_run(self.other, self.start, self.end)[0].payslips.get(user=self.outsider)

    def test_i_see_only_my_own_slips_and_figures(self):
        self.login("dev")
        r = self.get("me/")
        d = r.json()
        self.assertEqual([p["id"] for p in d["payslips"]], [self.mine.pk])
        self.assertNotIn("9999", r.content.decode())
        self.assertNotIn("colleague", r.content.decode())
        self.assertEqual((d["on_payroll"], d["is_admin"]), (True, False))
        self.assertEqual(self.get(f"me/{self.mine.pk}/").json()["daily_rate"], "1200.00")

    def test_a_colleagues_or_another_companys_slip_is_404_not_403(self):
        self.login("dev")
        self.assertEqual(self.get(f"me/{self.theirs.pk}/").status_code, 404)
        self.assertEqual(self.get(f"me/{self.foreign.pk}/").status_code, 404)

    def test_an_employee_cannot_use_the_admin_route_but_an_admin_can_use_mine(self):
        self.login("dev")
        self.assertEqual(self.get(f"payslips/{self.mine.pk}/").status_code, 403)
        self.login("owner")
        self.assertEqual(self.get("me/").status_code, 200)
        self.login("bot")
        self.assertEqual(self.get("me/").status_code, 200)  # a viewer reads their own

    def test_not_on_payroll_is_said_not_hidden(self):
        self.profile(self.bot, "0.00", on_payroll=False)
        self.login("bot")
        self.assertFalse(self.get("me/").json()["on_payroll"])


class LatenessApiTest(P):
    def setUp(self):
        super().setUp()
        self.profile(self.dev, "1000.00")
        for day, at in ((date(2026, 11, 2), time(10, 20)), (date(2026, 11, 3), time(11, 30))):
            AttendanceRecord.objects.create(
                company=self.company, user=self.dev, date=day,
                check_in=timezone.make_aware(datetime.combine(day, at)), check_out=timezone.make_aware(datetime.combine(day, time(19, 0))),
            )
        self.run, _ = service.generate_run(self.company, self.start, self.end)
        self.slip = self.run.payslips.get(user=self.dev)

    def test_the_admin_and_the_employee_both_get_every_late_day_and_its_cost(self):
        for who, path in (("owner", f"payslips/{self.slip.pk}/"), ("dev", f"me/{self.slip.pk}/")):
            self.login(who)
            d = self.get(path).json()
            reasons = " ".join(e["reason"] for e in d["late_events"])
            self.assertIn("2026-11-02", reasons, who)
            self.assertIn("20 min after", reasons)
            self.assertIn("2026-11-03", reasons)
            self.assertEqual({e["band"] for e in d["late_events"]} >= {"half_day"}, True)
            self.assertEqual(d["late_penalty"], "50.00")
            self.assertEqual(d["late_half_days"], "1.00")

    def test_an_on_time_slip_has_no_late_events_and_the_salary_breakdown_is_exposed(self):
        clean = make_user("clean", self.company)
        PayrollProfile.objects.create(company=self.company, user=clean, monthly_salary=Decimal("24000"), daily_rate=Decimal("0"), is_on_payroll=True, effective_from=date(2026, 1, 1))
        service.generate_run(self.company, self.start, self.end)
        slip = self.run.payslips.get(user=clean)
        self.login("owner")
        d = self.get(f"payslips/{slip.pk}/").json()
        self.assertEqual((d["late_events"], d["monthly_salary"], d["divisor_days"]), ([], "24000.00", 23))

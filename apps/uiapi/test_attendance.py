from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import corrections, service
from apps.attendance.models import AttendanceCorrection, AttendanceRecord
from apps.dashboards.models import ActivityLog
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.notifications.models import Notification

User = get_user_model()


def make(username, company, role):
    user = User.objects.create_user(username, f"{username}@test.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other_company = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.company, "owner")
        self.admin = make("admin", self.company, "admin")
        self.dev = make("dev", self.company, "developer")
        self.viewer = make("viewer", self.company, "viewer")
        self.outsider = make("outsider", self.other_company, "owner")
        self.today = timezone.localdate()

    def login(self, name, company=None):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = (company or self.company).pk
        s.save()

    def at(self, hour, minute=0, days_ago=0):
        return timezone.make_aware(datetime.combine(self.today - timedelta(days=days_ago), time(hour, minute)))

    def record(self, user=None, days_ago=0, inn=(9, 0), out=(17, 30), **kw):
        day = self.today - timedelta(days=days_ago)
        return AttendanceRecord.objects.create(
            company=kw.pop("company", self.company), user=user or self.dev, date=day, check_in=self.at(*inn, days_ago=days_ago) if inn else None,
            check_out=self.at(*out, days_ago=days_ago) if out else None, **kw,
        )

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")

    def me(self, **params):
        return self.client.get("/ui-api/v1/attendance/me/", params)


class PunchApiTest(Base):
    def punch(self):
        return self.post("/ui-api/v1/attendance/punch/")

    def test_check_in_then_out_logs_and_notifies_once_each(self):
        self.login("dev")
        r = self.punch()
        self.assertEqual((r.json()["action"], r.json()["ok"]), ("checked_in", True))
        rec = AttendanceRecord.objects.get(user=self.dev)
        self.assertIsNotNone(rec.check_in)
        rec.check_in = timezone.now() - timedelta(hours=3)
        rec.save()
        self.assertEqual(self.punch().json()["action"], "checked_out")
        self.assertEqual(self.punch().json()["action"], "unchanged")  # a third punch is a no-op
        self.assertEqual(ActivityLog.objects.filter(event_type="attendance_checked_in").count(), 1)
        self.assertEqual(ActivityLog.objects.filter(event_type="attendance_checked_out").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.dev, kind=Notification.Kind.SYSTEM).count(), 2)

    def test_a_second_tap_right_after_checking_in_is_ignored_and_says_so(self):
        self.login("dev")
        self.punch()
        r = self.punch().json()
        self.assertEqual((r["action"], r["ok"]), ("too_soon", False))
        self.assertIn("Give it a minute", r["message"])
        self.assertIsNone(AttendanceRecord.objects.get(user=self.dev).check_out)

    def test_every_role_can_punch_into_the_active_company_only(self):
        self.login("viewer")
        self.assertEqual(self.punch().json()["action"], "checked_in")
        self.assertEqual(AttendanceRecord.objects.get(user=self.viewer).company, self.company)
        self.assertEqual(AttendanceRecord.objects.filter(company=self.other_company).count(), 0)

    def test_anonymous_cannot_punch(self):
        self.assertIn(Client().post("/ui-api/v1/attendance/punch/", {}, content_type="application/json").status_code, (401, 403))


class MyAttendanceApiTest(Base):
    def test_a_member_sees_their_own_page_and_not_anyone_elses(self):
        self.record(user=self.dev)
        self.record(user=self.owner)
        self.login("dev")
        d = self.me().json()
        self.assertEqual((len(d["records"]), d["focus_user"], d["can_edit"], d["panel"]["readonly"]), (1, None, False, False))
        self.assertEqual(self.me(user_id=self.owner.pk).status_code, 403)

    def test_an_admin_reads_a_colleague_without_a_punch_button_and_never_another_companys_person(self):
        self.record(user=self.dev, days_ago=2, out=None)  # forgotten check-out
        self.login("admin")
        d = self.me(user_id=self.dev.pk).json()
        self.assertEqual((d["focus_user"]["name"], d["panel"]["readonly"], d["can_edit"]), ("dev", True, True))
        self.assertEqual([m["id"] for m in d["panel"]["missing_checkouts"]], [AttendanceRecord.objects.get(user=self.dev).pk])  # the colleague's warning, not the admin's
        self.assertEqual(self.me(user_id=self.outsider.pk).status_code, 404)
        self.assertEqual(self.me(user_id="²").status_code, 404)

    def test_the_panel_walks_ready_open_done(self):
        self.login("dev")
        p = self.me().json()["panel"]
        self.assertEqual((p["state"], p["can_punch"], p["since_ms"]), ("ready", True, None))
        self.assertRegex(p["shift_label"], r"–")
        rec = self.record(inn=None, out=None)
        rec.check_in = timezone.now() - timedelta(minutes=90)
        rec.save()
        p = self.me().json()["panel"]
        self.assertEqual(p["state"], "open")
        self.assertIsInstance(p["since_ms"], int)
        self.assertGreater(p["day_end_ms"], p["since_ms"])
        self.assertTrue(p["elapsed"])
        rec.check_out = timezone.now()
        rec.save()
        p = self.me().json()["panel"]
        self.assertEqual((p["state"], p["can_punch"]), ("done", False))
        self.assertTrue(p["worked"])

    def test_lateness_is_the_payslip_number_not_a_second_rule(self):
        shift = service.shift_for(self.company)
        late_by = shift.grace_minutes + 10
        start = timezone.make_aware(datetime.combine(self.today, shift.start_time)) + timedelta(minutes=late_by)
        rec = AttendanceRecord.objects.create(company=self.company, user=self.dev, date=self.today, check_in=start)
        self.login("dev")
        p = self.me().json()["panel"]
        self.assertEqual(p["late_minutes"], service.lateness_for(rec, shift))
        self.assertEqual(p["late_band"], service.late_penalty_for(rec, shift)["band"])
        rules = p["late_rules"]
        self.assertEqual((rules["grace"], rules["minorEnd"], rules["majorEnd"]), (shift.grace_minutes, shift.minor_band_end_minutes, shift.major_band_end_minutes))

    def test_the_forgotten_day_warning_spans_every_month_and_skips_today_and_colleagues(self):
        self.record(user=self.dev, days_ago=45, out=None)
        self.record(user=self.owner, days_ago=3, out=None)
        today_open = self.record(user=self.dev, out=None)
        self.login("dev")
        d = self.me().json()
        self.assertEqual(len(d["panel"]["missing_checkouts"]), 1)
        self.assertNotIn(today_open.pk, [m["id"] for m in d["panel"]["missing_checkouts"]])
        self.record(user=self.dev, days_ago=1)  # a closed day adds no warning
        self.assertEqual(len(self.me().json()["panel"]["missing_checkouts"]), 1)

    def test_a_forgotten_day_is_not_called_live_and_an_open_day_today_is_on_the_clock(self):
        stale = self.record(days_ago=2, out=None)
        live = AttendanceRecord.objects.create(company=self.company, user=self.dev, date=self.today, check_in=timezone.now() - timedelta(minutes=30))
        self.login("dev")
        by = {r["id"]: r for r in self.me().json()["records"]}
        self.assertEqual((by[stale.pk]["status"], by[live.pk]["status"]), ("stale", "open"))
        self.assertGreaterEqual(by[stale.pk]["open_days"], 2)
        self.assertEqual(self.me().json()["month"]["unclosed_days"], 1 if stale.date.month == self.today.month else 0)

    def test_the_week_strip_has_seven_days(self):
        self.record()
        self.login("dev")
        w = self.me().json()["panel"]["week"]
        self.assertEqual(len(w["days"]), 7)
        self.assertEqual(sum(1 for d in w["days"] if d["is_today"]), 1)

    def test_months_change_the_rows_not_just_the_label(self):
        self.record(days_ago=0)
        old = self.record(days_ago=40)
        self.login("dev")
        cur = self.me().json()
        self.assertEqual(len(cur["records"]), 1 if old.date.month != self.today.month else 2)
        past = self.me(month=old.date.strftime("%Y-%m")).json()
        self.assertEqual([r["id"] for r in past["records"]][-1], old.pk)
        self.assertEqual(past["month"]["current"], old.date.strftime("%Y-%m"))
        self.assertEqual(self.me(month="1999-01").json()["records"], [])
        self.assertEqual(self.me(month="2026-13-x").json()["month"]["current"], self.today.strftime("%Y-%m"))  # junk falls back to now

    def test_the_month_summary_tells_full_part_missing_and_future_apart(self):
        weekdays = [d for d in (self.today - timedelta(days=i) for i in range(1, 12)) if d.weekday() < 5 and d.month == self.today.month]
        if len(weekdays) < 2:
            self.skipTest("needs two weekdays earlier this month")
        full, part = weekdays[0], weekdays[1]
        AttendanceRecord.objects.create(company=self.company, user=self.dev, date=full, check_in=self.at(9, days_ago=(self.today - full).days), check_out=self.at(18, days_ago=(self.today - full).days))
        AttendanceRecord.objects.create(company=self.company, user=self.dev, date=part, check_in=self.at(9, days_ago=(self.today - part).days), check_out=self.at(10, days_ago=(self.today - part).days))
        self.login("dev")
        m = self.me().json()["month"]
        cells = {c["day"]: c for c in m["cells"]}
        self.assertEqual((cells[full.day]["state"], cells[part.day]["state"]), ("full", "part"))
        self.assertEqual(m["present_days"], 2)
        self.assertEqual(m["leading_blanks"], self.today.replace(day=1).weekday())
        self.assertGreaterEqual(m["counts"]["none"], 0)
        if self.today.day < 28:
            self.assertEqual(cells[self.today.day + 1]["state"], "future")  # not called missing

    def test_my_requests_are_listed_only_on_my_own_page(self):
        AttendanceCorrection.objects.create(company=self.company, user=self.dev, date=self.today, reason="forgot")
        self.login("dev")
        self.assertEqual([c["reason"] for c in self.me().json()["my_corrections"]], ["forgot"])
        self.login("admin")
        self.assertEqual(self.me(user_id=self.dev.pk).json()["my_corrections"], [])


class TeamApiTest(Base):
    def team(self, **params):
        return self.client.get("/ui-api/v1/attendance/team/", params)

    def test_admin_only_and_company_only(self):
        self.record(user=self.dev)
        self.login("dev")
        self.assertEqual(self.team().status_code, 403)
        self.assertEqual(self.client.get("/ui-api/v1/attendance/timesheet/").status_code, 403)
        self.login("outsider", self.other_company)
        names = [r["user"]["name"] for r in self.team().json()["rows"]]
        self.assertEqual(names, ["outsider"])
        self.login("owner")
        self.assertNotIn("outsider", [r["user"]["name"] for r in self.team().json()["rows"]])

    def test_your_row_is_first_every_row_has_seven_days_and_no_email_leaks(self):
        self.record(user=self.dev)
        self.login("admin")
        d = self.team().json()
        self.assertEqual(d["rows"][0]["user"]["name"], "admin")
        self.assertTrue(d["rows"][0]["user"]["is_me"])
        self.assertTrue(all(len(r["week"]) == 7 for r in d["rows"]))
        self.assertNotIn("@test.local", str(d))
        dev = next(r for r in d["rows"] if r["user"]["username"] == "dev")
        self.assertEqual((dev["has_punch"], dev["record_id"] is not None), (True, True))

    def test_forgotten_days_are_listed_with_their_fix_and_counted(self):
        stale = self.record(user=self.dev, days_ago=2, out=None)
        self.login("owner")
        d = self.team().json()
        self.assertEqual([(o["record_id"], o["is_stale"]) for o in d["on_clock"]], [(stale.pk, True)])
        self.assertEqual((d["counts"]["on_clock"], d["counts"]["stale"]), (1, 1))

    def test_leave_is_counted_separately_from_absent_and_pending_leave_is_not_leave(self):
        policy = LeavePolicy.objects.create(company=self.company, name="Casual", max_days_per_year=12)
        LeaveRequest.objects.create(company=self.company, user=self.dev, policy=policy, start_date=self.today, end_date=self.today, days=1, status="approved")
        LeaveRequest.objects.create(company=self.company, user=self.viewer, policy=policy, start_date=self.today, end_date=self.today, days=1, status="pending")
        self.login("owner")
        d = self.team().json()
        states = {r["user"]["username"]: r["state"] for r in d["rows"]}
        self.assertEqual(states["dev"], "leave")
        self.assertNotEqual(states["viewer"], "leave")
        self.assertEqual(d["counts"]["leave"], 1)
        self.assertEqual(d["counts"]["team"], 4)

    def test_week_view(self):
        monday = self.today - timedelta(days=self.today.weekday())
        self.record(user=self.dev, days_ago=self.today.weekday())
        self.login("admin")
        d = self.team(view="week").json()
        self.assertEqual((d["view"], d["monday"], len(d["days"]), d["is_this_week"]), ("week", monday.isoformat(), 7, True))
        row = next(r for r in d["rows"] if r["user"]["username"] == "dev")
        self.assertEqual(row["days"][0]["state"], "worked")
        self.assertEqual(self.team(view="week", week="garbage").status_code, 200)
        prev = self.team(view="week", week=d["prev"]).json()
        self.assertFalse(prev["is_this_week"])


class TimesheetApiTest(Base):
    def test_month_rows_count_present_leave_and_unclosed_days(self):
        self.record(user=self.dev, days_ago=0)
        self.record(user=self.dev, days_ago=1, out=None)
        self.login("owner")
        d = self.client.get("/ui-api/v1/attendance/timesheet/").json()
        row = next(r for r in d["rows"] if r["user"]["username"] == "dev")
        present = 2 if (self.today - timedelta(days=1)).month == self.today.month else 1
        self.assertEqual(row["present_days"], present)
        self.assertIn("h", d["company_total"])
        self.assertEqual(len(d["rows"]), 4)  # everyone, punches or not
        self.assertEqual(self.client.get("/ui-api/v1/attendance/timesheet/", {"month": "2026-02"}).json()["month"]["current"], "2026-02")

    def test_detail_grid_is_scoped_to_the_company(self):
        self.record(user=self.dev)
        self.login("owner")
        d = self.client.get(f"/ui-api/v1/attendance/timesheet/{self.dev.pk}/").json()
        self.assertEqual((d["user"]["name"], d["totals"]["present"]), ("dev", 1))
        today_cell = next(c for c in d["days"] if c["is_today"])
        self.assertTrue(today_cell["record_id"])
        self.assertEqual(self.client.get(f"/ui-api/v1/attendance/timesheet/{self.outsider.pk}/").status_code, 404)

    def test_the_grid_marks_leave_and_a_forgotten_day(self):
        policy = LeavePolicy.objects.create(company=self.company, name="Casual", max_days_per_year=12)
        LeaveRequest.objects.create(company=self.company, user=self.dev, policy=policy, start_date=self.today.replace(day=1), end_date=self.today.replace(day=1), days=1, status="approved")
        self.record(user=self.dev, days_ago=0, out=None)
        self.login("admin")
        d = self.client.get(f"/ui-api/v1/attendance/timesheet/{self.dev.pk}/").json()
        self.assertTrue(d["days"][0]["on_leave"])
        self.assertEqual(d["totals"]["leave"], 1)


class RecordEditApiTest(Base):
    def url(self, rec):
        return f"/ui-api/v1/attendance/records/{rec.pk}/"

    def patch(self, rec, **body):
        return self.client.patch(self.url(rec), body, content_type="application/json")

    def local(self, hour, minute=0, days_ago=0):
        return f"{(self.today - timedelta(days=days_ago)).isoformat()}T{hour:02d}:{minute:02d}"

    def test_an_admin_edits_and_it_is_logged_and_marked_edited(self):
        rec = self.record(days_ago=1, out=None)
        self.login("admin")
        r = self.patch(rec, check_in=self.local(9, 15, 1), check_out=self.local(17, 45, 1), notes="fixed")
        self.assertEqual(r.status_code, 200)
        rec.refresh_from_db()
        self.assertEqual((rec.is_edited, rec.notes, timezone.localtime(rec.check_out).hour), (True, "fixed", 17))
        self.assertTrue(ActivityLog.objects.filter(event_type="attendance_edited", actor=self.admin).exists())
        self.assertFalse(r.json()["warning"])

    def test_clearing_the_check_out_keeps_the_day_open_and_warns(self):
        rec = self.record(days_ago=1)
        self.login("owner")
        r = self.patch(rec, check_in=self.local(9, 0, 1), check_out="")
        self.assertTrue(r.json()["warning"])
        rec.refresh_from_db()
        self.assertIsNone(rec.check_out)

    def test_validation(self):
        rec = self.record(days_ago=1)
        self.login("owner")
        self.assertEqual(self.patch(rec, check_in=self.local(10, 0, 1), check_out=self.local(9, 0, 1)).status_code, 400)  # out before in
        self.assertEqual(self.patch(rec, check_in=self.local(9, 0, 3), check_out=self.local(17, 0, 3)).status_code, 400)  # another day
        future = (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(self.patch(rec, check_in=self.local(9, 0, 1), check_out=future).status_code, 400)
        empty = AttendanceRecord.objects.create(company=self.company, user=self.dev, date=self.today - timedelta(days=5))
        self.assertEqual(self.patch(empty, check_in="", check_out="").status_code, 400)  # would store an empty row
        rec.refresh_from_db()
        self.assertFalse(rec.is_edited)

    def test_a_night_shift_may_close_the_next_morning(self):
        rec = self.record(days_ago=3, inn=(22, 0), out=None)
        self.login("owner")
        r = self.patch(rec, check_in=self.local(22, 0, 3), check_out=self.local(6, 0, 2))
        self.assertEqual(r.status_code, 200)

    def test_only_admins_edit_and_only_in_their_company(self):
        rec = self.record(days_ago=1)
        theirs = self.record(user=self.outsider, company=self.other_company)
        self.login("dev")
        self.assertEqual(self.patch(rec, check_in=self.local(9, 0, 1)).status_code, 403)
        self.assertEqual(self.client.get(self.url(rec)).status_code, 403)
        self.login("owner")
        self.assertEqual(self.patch(theirs, check_in=self.local(9, 0)).status_code, 404)
        self.assertEqual(self.client.get(self.url(theirs)).status_code, 404)

    def test_the_form_is_prefilled_and_offers_the_end_of_the_shift_for_a_forgotten_day(self):
        rec = self.record(days_ago=2, out=None)
        self.login("owner")
        d = self.client.get(self.url(rec)).json()
        self.assertEqual((d["check_in"][-5:], d["check_out"], d["status"]), ("09:00", "", "stale"))
        self.assertTrue(d["suggested_check_out"].startswith(rec.date.isoformat()))


class CorrectionApiTest(Base):
    def request(self, day=None, **over):
        day = day or self.today - timedelta(days=1)
        return self.post("/ui-api/v1/attendance/corrections/request/", {"date": day.isoformat(), "check_in": "09:00", "check_out": "17:30", "reason": "forgot to punch", **over})

    def test_the_form_state_shows_what_is_recorded_and_the_limits(self):
        self.record(days_ago=1)
        self.login("dev")
        yesterday = self.today - timedelta(days=1)
        d = self.client.get("/ui-api/v1/attendance/corrections/request/", {"date": yesterday.isoformat()}).json()
        self.assertEqual((d["record"]["check_in"], d["max_age_days"], d["max_date"]), ("9:00 AM", 60, self.today.isoformat()))
        self.assertEqual(self.client.get("/ui-api/v1/attendance/corrections/request/", {"date": "junk"}).json()["date"], self.today.isoformat())

    def test_a_valid_request_is_saved_and_after_midnight_goes_to_the_next_day(self):
        self.login("dev")
        r = self.request(check_out="01:30", out_next_day=True)
        self.assertEqual(r.status_code, 201)
        self.assertIn("Request sent", r.json()["message"])
        c = AttendanceCorrection.objects.get()
        self.assertEqual(timezone.localtime(c.requested_check_out).date(), c.date + timedelta(days=1))

    def test_bad_requests_are_a_message_not_a_crash(self):
        self.login("dev")
        for over in ({"reason": ""}, {"check_in": "nine"}, {"check_in": "", "check_out": ""}, {"date": (self.today + timedelta(days=1)).isoformat()},
                     {"date": (self.today - timedelta(days=corrections.MAX_AGE_DAYS + 5)).isoformat()}):
            r = self.request(**over)
            self.assertEqual(r.status_code, 400, over)
            self.assertTrue(r.json()["detail"])
        self.assertFalse(AttendanceCorrection.objects.exists())
        self.assertEqual(self.request().status_code, 201)
        self.assertEqual(self.request().status_code, 400)  # one open request per day

    def test_the_queue_is_for_owners_and_admins_and_flags_your_own(self):
        AttendanceCorrection.objects.create(company=self.company, user=self.dev, date=self.today - timedelta(days=1), reason="a")
        self.login("dev")
        self.assertEqual(self.client.get("/ui-api/v1/attendance/corrections/").status_code, 403)
        self.login("owner")
        d = self.client.get("/ui-api/v1/attendance/corrections/").json()
        self.assertEqual([(c["person"]["name"], c["can_decide"], c["is_mine"]) for c in d["pending"]], [("dev", True, False)])

    def test_an_owner_approves_through_the_queue_and_it_applies(self):
        self.record(days_ago=1, inn=(10, 0), out=(16, 0))
        self.login("dev")
        self.request()
        c = AttendanceCorrection.objects.get()
        self.login("owner")
        r = self.post(f"/ui-api/v1/attendance/corrections/{c.pk}/approve/", {"note": "ok"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("approved", r.json()["message"])
        c.refresh_from_db()
        rec = AttendanceRecord.objects.get(user=self.dev)
        self.assertEqual((c.status, rec.is_edited, timezone.localtime(rec.check_in).hour), ("approved", True, 9))
        again = self.post(f"/ui-api/v1/attendance/corrections/{c.pk}/approve/")
        self.assertEqual(again.status_code, 400)  # already dealt with
        self.assertTrue(Notification.objects.filter(user=self.dev, kind=Notification.Kind.CORRECTION_DECISION).exists())

    def test_rejecting_leaves_the_record_alone(self):
        self.record(days_ago=1, inn=(10, 0), out=(16, 0))
        self.login("dev")
        self.request()
        c = AttendanceCorrection.objects.get()
        self.login("admin")
        self.post(f"/ui-api/v1/attendance/corrections/{c.pk}/reject/", {"note": "no"})
        rec = AttendanceRecord.objects.get(user=self.dev)
        self.assertEqual((timezone.localtime(rec.check_in).hour, rec.is_edited), (10, False))

    def test_who_may_decide_and_which_actions_exist(self):
        c = AttendanceCorrection.objects.create(company=self.company, user=self.dev, date=self.today - timedelta(days=1), reason="a", requested_check_in=self.at(9, days_ago=1))
        foreign = AttendanceCorrection.objects.create(company=self.other_company, user=self.outsider, date=self.today - timedelta(days=1), reason="x")
        self.login("dev")
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{c.pk}/approve/").status_code, 403)
        self.login("owner")
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{c.pk}/delete/").status_code, 403)
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{foreign.pk}/approve/").status_code, 404)
        c.refresh_from_db()
        self.assertEqual(c.status, "pending")

    def test_cancelling_only_your_own_and_it_is_audited(self):
        mine = AttendanceCorrection.objects.create(company=self.company, user=self.dev, date=self.today - timedelta(days=1), reason="a")
        theirs = AttendanceCorrection.objects.create(company=self.company, user=self.viewer, date=self.today - timedelta(days=2), reason="b")
        self.login("dev")
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{theirs.pk}/cancel/").status_code, 404)
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{mine.pk}/cancel/").status_code, 200)
        mine.refresh_from_db()
        self.assertEqual(mine.status, "cancelled")
        self.assertTrue(ActivityLog.objects.filter(event_type="attendance_correction_cancelled").exists())
        self.assertEqual(self.post(f"/ui-api/v1/attendance/corrections/{mine.pk}/cancel/").status_code, 400)

    def test_a_lone_owner_may_decide_their_own_request_but_not_when_there_is_another_admin(self):
        c = AttendanceCorrection.objects.create(company=self.company, user=self.owner, date=self.today - timedelta(days=1), reason="a", requested_check_in=self.at(9, days_ago=1))
        self.login("owner")
        d = self.client.get("/ui-api/v1/attendance/corrections/").json()
        self.assertFalse(d["pending"][0]["can_decide"])  # an admin exists
        Membership.objects.filter(user=self.admin).update(role="developer")
        self.assertTrue(self.client.get("/ui-api/v1/attendance/corrections/").json()["pending"][0]["can_decide"])
        self.assertEqual(c.status, "pending")


class ShellPagesTest(Base):
    def test_pages_serve_the_shell_with_the_old_rights(self):
        rec = self.record()
        member_pages = ["/attendance/", "/attendance/corrections/request/"]
        admin_pages = ["/attendance/team/", "/attendance/timesheet/", f"/attendance/timesheet/{self.dev.pk}/", "/attendance/corrections/", f"/attendance/{rec.pk}/edit/"]
        self.login("dev")
        for url in member_pages:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html")
        for url in admin_pages:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.login("admin")
        for url in member_pages + admin_pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        theirs = self.record(user=self.outsider, company=self.other_company)
        self.assertEqual(self.client.get(f"/attendance/{theirs.pk}/edit/").status_code, 404)
        for url in member_pages + admin_pages:
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_the_old_routes_and_templates_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        from django.urls import NoReverseMatch, reverse

        for name, args in (("punch", []), ("correction_cancel", [1]), ("correction_decision", [1, "approve"])):
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(f"attendance:{name}", args=args)
        with self.assertRaises(TemplateDoesNotExist):
            get_template("attendance/my_attendance.html")

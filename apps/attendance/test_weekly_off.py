"""Weekly off days: the company decides them, and work on one carries no rules.

Dates are fixed (2026-10-17 is a Saturday, 2026-10-19 a Monday) so the lateness
tests pass on any day the suite runs. Tests that go through a view, which reads
the real "today", change the setting instead of waiting for a weekend.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.attendance import reminders, service
from apps.attendance.models import AttendanceRecord, WorkShift, weekly_off_for
from apps.dashboards.models import ActivityLog

User = get_user_model()

SATURDAY = date(2026, 10, 17)
SUNDAY = date(2026, 10, 18)
MONDAY = date(2026, 10, 19)


def at(day, h, m=0):
    return timezone.make_aware(datetime.combine(day, time(h, m)), timezone.get_current_timezone())


class WeeklyOffBase(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.owner = self.member("owner", "owner")
        self.dev = self.member("dev", "developer")

    def member(self, name, role):
        user = User.objects.create_user(name, f"{name}@test.local", "pass1234")
        Membership.objects.create(user=user, company=self.co, role=role)
        return user

    def record(self, day, h, m=0, user=None, out=(18, 30)):
        return AttendanceRecord.objects.create(
            company=self.co, user=user or self.dev, date=day,
            check_in=at(day, h, m), check_out=at(day, *out) if out else None,
        )

    def set_off(self, *weekdays):
        service.set_weekly_off(self.co, [str(d) for d in weekdays])

    def today_off(self, off=True):
        """Make today a weekly off (or a working day) whatever day the suite runs."""
        self.set_off(*([timezone.localdate().weekday()] if off else []))


class SettingTest(WeeklyOffBase):
    def test_saturday_and_sunday_are_off_unless_changed(self):
        self.assertEqual(service.shift_for(self.co).weekly_off_days, [5, 6])
        self.assertEqual(weekly_off_for(self.co), {5, 6})

    def test_reading_the_days_does_not_create_a_shift_row(self):
        other = Company.objects.create(name="Other", slug="other")
        self.assertEqual(weekly_off_for(other), {5, 6})
        self.assertFalse(WorkShift.objects.filter(company=other).exists())

    def test_set_weekly_off_saves_sorted_days(self):
        self.assertEqual(service.set_weekly_off(self.co, ["6", "4", "4"]), [4, 6])
        self.assertEqual(weekly_off_for(self.co), {4, 6})
        self.assertEqual(service.weekly_off_label([4, 6]), "Friday, Sunday")
        self.assertEqual(service.weekly_off_label([4, 6], short=True), "Fri, Sun")

    def test_no_weekly_off_at_all_is_a_seven_day_week(self):
        self.assertEqual(service.set_weekly_off(self.co, []), [])
        self.assertFalse(service.shift_for(self.co).is_weekly_off(SATURDAY))

    def test_nonsense_and_a_week_with_no_working_day_are_refused(self):
        for bad in (["7"], ["x"], ["-1"], [None], [str(n) for n in range(7)]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    service.set_weekly_off(self.co, bad)
        self.assertEqual(weekly_off_for(self.co), {5, 6})


class NoRulesOnAnOffDayTest(WeeklyOffBase):
    def test_a_late_punch_on_a_saturday_is_free_but_the_same_on_a_monday_is_not(self):
        sat = self.record(SATURDAY, 11, 30, user=self.dev)
        mon = self.record(MONDAY, 11, 30, user=self.dev)
        self.assertEqual(service.lateness_for(sat), 0)
        self.assertIsNone(service.late_penalty_for(sat))
        self.assertIsNone(service.late_label_for(sat, service.shift_for(self.co)))
        self.assertEqual(service.lateness_for(mon), 90)
        self.assertEqual(service.late_penalty_for(mon)["band"], "half_day")

    def test_every_band_applies_on_a_monday_and_none_on_a_saturday(self):
        # 10:10 is inside the 15 minute grace; 12:10 is over an hour late.
        cases = ((10, 10, None), (10, 20, "minor"), (10, 45, "major"), (12, 10, "half_day"))
        for week, (h, m, band) in enumerate(cases):
            monday = self.record(MONDAY + timedelta(weeks=week), h, m)
            saturday = self.record(SATURDAY + timedelta(weeks=week), h, m)
            with self.subTest(arrives=f"{h}:{m:02d}"):
                penalty = service.late_penalty_for(monday)
                self.assertEqual(penalty and penalty["band"], band)
                self.assertIsNone(service.late_penalty_for(saturday))

    def test_changing_the_off_days_moves_the_penalty(self):
        sat = self.record(SATURDAY, 11, 30)
        mon = self.record(MONDAY, 11, 30)
        self.set_off(0)  # Monday is the weekly off, Saturday is a working day now
        self.assertIsNone(service.late_penalty_for(mon))
        self.assertEqual(service.late_penalty_for(sat)["band"], "half_day")
        self.set_off()  # no weekly off at all
        self.assertEqual(service.late_penalty_for(mon)["band"], "half_day")
        self.assertEqual(service.late_penalty_for(sat)["band"], "half_day")

    def test_an_off_day_is_not_an_absence_in_the_month_grid(self):
        # October 2026 has 9 Saturdays and Sundays, 4 of them Sundays.
        absent = lambda: service.get_month_grid(self.co, 2026, 10, self.dev)["absent_days"]
        self.assertEqual(absent(), 31 - 9)
        self.set_off(6)
        self.assertEqual(absent(), 31 - 4)
        self.set_off()
        self.assertEqual(absent(), 31)
        grid = service.get_month_grid(self.co, 2026, 10, self.dev)
        self.assertFalse(any(d["is_weekend"] for d in grid["days"]))

    def test_the_team_week_shows_the_companys_off_days_as_rest(self):
        monday = date(2020, 3, 2)
        states = lambda: [
            c["state"]
            for r in service.get_team_week(self.co, monday) if r["user"] == self.dev
            for c in r["days"]
        ]
        self.assertEqual(states(), ["none"] * 5 + ["weekend"] * 2)
        self.set_off(0)
        self.assertEqual(states(), ["weekend"] + ["none"] * 6)

    def test_work_on_an_off_day_is_listed_without_a_late_tag(self):
        self.record(date(2020, 3, 7), 14, 0)  # a Saturday afternoon
        cell = next(r for r in service.get_team_week(self.co, date(2020, 3, 2)) if r["user"] == self.dev)["days"][5]
        self.assertEqual((cell["state"], cell["band"], cell["late_minutes"]), ("worked", None, 0))
        self.set_off(6)
        cell = next(r for r in service.get_team_week(self.co, date(2020, 3, 2)) if r["user"] == self.dev)["days"][5]
        self.assertEqual(cell["band"], "half_day")


class PunchPanelTest(WeeklyOffBase):
    def open_panel(self):
        self.client.login(username="dev", password="pass1234")
        return self.client.get(reverse("attendance:my_attendance")).content.decode()

    def test_the_idle_panel_drops_the_shift_rules_on_an_off_day(self):
        self.today_off()
        page = self.open_panel()
        self.assertIn("Weekly off: no shift start, grace period, penalty or half day applies today.", page)
        self.assertNotIn('x-text="lateNote.text"', page)
        self.assertNotIn("A 8h 00m working day", page)
        self.assertIn("Check in", page)  # still punchable

    def test_the_idle_panel_keeps_them_on_a_working_day(self):
        self.today_off(False)
        page = self.open_panel()
        self.assertIn('x-text="lateNote.text"', page)
        self.assertIn("A 8h 00m working day", page)
        self.assertNotIn("Weekly off: no shift start", page)

    def test_a_short_day_is_not_called_short_on_an_off_day(self):
        now = timezone.now()
        AttendanceRecord.objects.create(
            company=self.co, user=self.dev, date=timezone.localdate(),
            check_in=now - timedelta(minutes=50), check_out=now - timedelta(minutes=5),
        )
        self.today_off()
        page = self.open_panel()
        self.assertIn("No target hours on a weekly off", page)
        self.assertNotIn("short of the", page)
        self.assertNotIn('punch-ontime">on time', page)
        self.today_off(False)
        self.assertIn("short of the", self.open_panel())

    def test_the_running_counter_is_elapsed_time_not_a_countdown_on_an_off_day(self):
        AttendanceRecord.objects.create(
            company=self.co, user=self.dev, date=timezone.localdate(),
            check_in=timezone.now() - timedelta(minutes=50),
        )
        self.today_off()
        page = self.open_panel()
        self.assertIn("Weekly off, check out whenever you finish", page)
        self.assertNotIn("left in your day</span>", page)
        self.assertNotIn("Full day done at", page)

    def test_the_punch_notification_has_no_shift_wording_on_an_off_day(self):
        from apps.attendance.views import _punch_notification_body as body

        sat = self.record(SATURDAY, 11, 30, out=(14, 0))
        self.assertEqual(body(sat, "checked_in", self.co), "Weekly off: no shift start, lateness or late fee today.")
        self.assertNotIn("short of", body(sat, "checked_out", self.co))
        self.assertIn("2h 30m worked today", body(sat, "checked_out", self.co))
        mon = self.record(MONDAY, 11, 30, out=(14, 0), user=self.owner)
        self.assertIn("half day", body(mon, "checked_in", self.co))
        self.assertIn("short of a full", body(mon, "checked_out", self.co))


class TeamPageTest(WeeklyOffBase):
    def team(self):
        self.client.login(username="owner", password="pass1234")
        return self.client.get(reverse("attendance:team_attendance"))

    def test_nobody_is_absent_on_a_weekly_off(self):
        self.today_off()
        page = self.team()
        self.assertEqual(page.context["absent_count"], 0)
        self.assertEqual({r["state"] for r in page.context["team"]}, {"off"})
        self.assertContains(page, "Weekly off</span>")
        self.assertNotContains(page, 'pill closed">Absent')

    def test_the_same_people_are_absent_on_a_working_day(self):
        self.today_off(False)
        page = self.team()
        self.assertEqual(page.context["absent_count"], 2)
        self.assertContains(page, 'pill closed">Absent')

    def test_someone_who_works_an_off_day_is_listed_as_present(self):
        self.today_off()
        self.record(timezone.localdate(), 14, 0, out=None)
        page = self.team()
        self.assertEqual(page.context["present_count"], 1)
        self.assertEqual(page.context["absent_count"], 0)

    def test_the_week_view_marks_the_header_of_an_off_day(self):
        self.client.login(username="owner", password="pass1234")
        week = self.client.get(reverse("attendance:team_attendance"), {"view": "week", "week": "2020-03-02"})
        self.assertEqual([d["off"] for d in week.context["days"]], [False] * 5 + [True] * 2)
        self.set_off(0)
        week = self.client.get(reverse("attendance:team_attendance"), {"view": "week", "week": "2020-03-02"})
        self.assertEqual([d["off"] for d in week.context["days"]], [True] + [False] * 6)


class SettingScreenTest(WeeklyOffBase):
    url = property(lambda self: reverse("attendance:weekly_off"))

    def test_the_team_page_offers_the_current_days(self):
        self.client.login(username="owner", password="pass1234")
        page = self.client.get(reverse("attendance:team_attendance"))
        self.assertContains(page, "Weekly off: Sat, Sun")
        self.assertContains(page, 'name="off_days" value="5" checked')
        self.assertContains(page, 'name="off_days" value="6" checked')
        self.assertNotContains(page, 'name="off_days" value="0" checked')

    def test_an_owner_saves_the_days_and_is_told(self):
        self.client.login(username="owner", password="pass1234")
        res = self.client.post(self.url, {"off_days": ["4", "5"]}, follow=True)
        self.assertEqual(weekly_off_for(self.co), {4, 5})
        self.assertContains(res, 'id="toast-seed"')
        self.assertContains(res, "Weekly off days saved: Friday, Saturday.")
        log = ActivityLog.objects.get(company=self.co, event_type="weekly_off_changed")
        self.assertEqual((log.actor, log.metadata), (self.owner, {"days": [4, 5]}))

    def test_clearing_every_box_means_a_seven_day_week(self):
        self.client.login(username="owner", password="pass1234")
        res = self.client.post(self.url, {}, follow=True)
        self.assertEqual(weekly_off_for(self.co), frozenset())
        self.assertContains(res, "every day of the week is a working day")

    def test_bad_input_is_refused_and_nothing_changes(self):
        self.client.login(username="owner", password="pass1234")
        for data, message in (
            ({"off_days": [str(n) for n in range(7)]}, "Leave at least one working day."),
            ({"off_days": ["9"]}, "Pick weekdays from the list."),
        ):
            with self.subTest(data=data):
                res = self.client.post(self.url, data, follow=True)
                self.assertContains(res, message)
                self.assertEqual(weekly_off_for(self.co), {5, 6})

    def test_only_owners_and_admins_can_change_it(self):
        self.client.login(username="dev", password="pass1234")
        self.assertEqual(self.client.post(self.url, {"off_days": ["0"]}).status_code, 403)
        self.assertEqual(weekly_off_for(self.co), {5, 6})
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {"off_days": ["0"]}).status_code, 302)  # sent to sign in


class RemindersAndStreakTest(WeeklyOffBase):
    def setUp(self):
        super().setUp()
        self.record(date(2026, 10, 12), 10, 0)  # the dev uses attendance, so gets nudged

    def test_no_check_in_nudge_on_a_weekly_off_but_one_on_a_working_day(self):
        tuesday, saturday = date(2026, 10, 13), SATURDAY
        self.set_off(1)  # Tuesday off, Saturday working
        self.assertEqual(reminders.send(self.co, at(tuesday, 10, 10)), 0)
        self.assertEqual(reminders.send(self.co, at(saturday, 10, 10)), 1)

    def test_an_off_day_neither_counts_nor_breaks_the_on_time_streak(self):
        from apps.core import kudos

        self.record(date(2026, 10, 16), 10, 0, out=None)  # Friday, on time
        self.record(MONDAY, 10, 5, out=None)  # Monday, on time
        self.assertEqual(kudos.on_time_streak(self.co, self.dev, today=MONDAY), 2)
        self.set_off()  # now the weekend was working days nobody came in on
        self.assertEqual(kudos.on_time_streak(self.co, self.dev, today=MONDAY), 1)

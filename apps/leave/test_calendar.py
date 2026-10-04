from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.leave import service
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.notifications.models import Notification
from apps.payroll.models import Holiday

User = get_user_model()


def make(username, company, role="developer", approver=False, first=""):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234", first_name=first)
    Membership.objects.create(user=user, company=company, role=role, is_leave_approver=approver)
    return user


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.company, "owner", first="Olive")
        self.approver = make("approver", self.company, "developer", True, first="Abe")
        self.ann = make("ann", self.company, first="Ann")
        self.bob = make("bob", self.company, first="Bob")
        self.cat = make("cat", self.company, first="Cat")
        self.eve = make("eve", self.other, "owner")
        self.policy = LeavePolicy.objects.create(company=self.company, name="Casual", max_days_per_year=Decimal("20"))
        # A fixed Monday so the calendar maths does not depend on the day the tests run.
        self.mon = date(2030, 6, 3)

    def leave(self, user, start, end, status="approved", half=False, company=None):
        days = Decimal("0.5") if half else Decimal(len(service._weekdays_between(start, end)))
        return LeaveRequest.objects.create(
            company=company or self.company, user=user, policy=self.policy, start_date=start, end_date=end,
            is_half_day=half, days=days, paid_days=days, unpaid_days=Decimal("0"), status=status,
        )


class ClashTest(Base):
    def test_it_lists_who_else_is_off_and_the_busiest_day(self):
        self.leave(self.bob, self.mon, self.mon + timedelta(days=1))
        self.leave(self.cat, self.mon + timedelta(days=1), self.mon + timedelta(days=2))
        clash = service.clash_for(self.company, self.ann, self.mon, self.mon + timedelta(days=4))
        self.assertEqual(clash["people"], ["Bob", "Cat"])
        self.assertEqual((clash["peak"], clash["peak_day"]), (2, self.mon + timedelta(days=1)))
        self.assertEqual(clash["team"], 5)

    def test_you_do_not_clash_with_yourself(self):
        self.leave(self.ann, self.mon, self.mon)
        self.assertEqual(service.clash_for(self.company, self.ann, self.mon, self.mon)["people"], [])

    def test_only_approved_leave_counts(self):
        for status in ("pending", "rejected", "cancelled"):
            self.leave(self.bob, self.mon, self.mon, status=status)
        self.assertEqual(service.clash_for(self.company, self.ann, self.mon, self.mon)["people"], [])

    def test_weekends_and_holidays_are_not_clashes(self):
        sat = self.mon + timedelta(days=5)
        self.leave(self.bob, sat, sat + timedelta(days=1))
        Holiday.objects.create(company=self.company, date=self.mon, name="Fest")
        self.leave(self.cat, self.mon, self.mon)
        self.assertEqual(service.clash_for(self.company, self.ann, self.mon, sat + timedelta(days=1))["people"], [])

    def test_other_workspaces_never_count(self):
        theirs = LeavePolicy.objects.create(company=self.other, name="X")
        LeaveRequest.objects.create(company=self.other, user=self.eve, policy=theirs, start_date=self.mon, end_date=self.mon,
                                    days=Decimal("1"), paid_days=Decimal("1"), unpaid_days=Decimal("0"), status="approved")
        self.assertEqual(service.clash_for(self.company, self.ann, self.mon, self.mon)["people"], [])

    def test_the_request_being_reviewed_is_excluded(self):
        mine = self.leave(self.bob, self.mon, self.mon)
        self.assertEqual(service.clash_for(self.company, self.ann, self.mon, self.mon, exclude_pk=mine.pk)["people"], [])

    def test_the_sentence_is_empty_when_nobody_is_off(self):
        self.assertEqual(service.clash_sentence(service.clash_for(self.company, self.ann, self.mon, self.mon)), "")

    def test_the_sentence_names_people_and_the_head_count(self):
        self.leave(self.bob, self.mon, self.mon)
        text = service.clash_sentence(service.clash_for(self.company, self.ann, self.mon, self.mon))
        self.assertIn("Bob is also off", text)
        self.assertIn("1 of 5 away", text)


class CalendarTest(Base):
    def cal(self, show_types=False):
        return service.month_calendar(self.company, 2030, 6, show_types=show_types)

    def cell(self, cal, day):
        return next(d for w in cal["weeks"] for d in w if d["date"] == day)

    def test_weeks_start_on_monday_and_cover_the_month(self):
        cal = self.cal()
        self.assertTrue(all(len(w) == 7 for w in cal["weeks"]))
        self.assertEqual(cal["weeks"][0][0]["date"].weekday(), 0)
        self.assertEqual(cal["weeks"][-1][-1]["date"].weekday(), 6)
        in_month = [d["date"] for w in cal["weeks"] for d in w if d["in_month"]]
        self.assertEqual((in_month[0], in_month[-1]), (date(2030, 6, 1), date(2030, 6, 30)))

    def test_a_spell_shows_on_each_working_day_but_not_the_weekend(self):
        self.leave(self.bob, self.mon + timedelta(days=4), self.mon + timedelta(days=8))  # Fri to Tue
        cal = self.cal()
        shown = [d["date"] for w in cal["weeks"] for d in w if d["entries"]]
        self.assertEqual(shown, [self.mon + timedelta(days=4), self.mon + timedelta(days=7), self.mon + timedelta(days=8)])

    def test_pending_is_marked_and_listed_after_approved(self):
        self.leave(self.ann, self.mon, self.mon, status="pending")
        self.leave(self.bob, self.mon, self.mon)
        entries = self.cell(self.cal(), self.mon)["entries"]
        self.assertEqual([(e["name"], e["status"]) for e in entries], [("Bob", "approved"), ("Ann", "pending")])

    def test_rejected_and_cancelled_are_hidden(self):
        self.leave(self.bob, self.mon, self.mon, status="rejected")
        self.leave(self.cat, self.mon, self.mon, status="cancelled")
        self.assertEqual(self.cell(self.cal(), self.mon)["entries"], [])

    def test_a_holiday_is_named_and_hides_leave_that_day(self):
        Holiday.objects.create(company=self.company, date=self.mon, name="Founders day")
        self.leave(self.bob, self.mon, self.mon + timedelta(days=1))
        cal = self.cal()
        self.assertEqual(self.cell(cal, self.mon)["holiday"], "Founders day")
        self.assertEqual(self.cell(cal, self.mon)["entries"], [])
        self.assertEqual(len(self.cell(cal, self.mon + timedelta(days=1))["entries"]), 1)

    def test_leave_types_are_hidden_unless_asked_for(self):
        self.leave(self.bob, self.mon, self.mon)
        self.assertEqual(self.cell(self.cal(False), self.mon)["entries"][0]["policy"], "")
        self.assertEqual(self.cell(self.cal(True), self.mon)["entries"][0]["policy"], "Casual")

    def test_half_days_are_marked(self):
        self.leave(self.bob, self.mon, self.mon, half=True)
        self.assertTrue(self.cell(self.cal(), self.mon)["entries"][0]["half"])

    def test_the_off_count_counts_approved_only(self):
        self.leave(self.bob, self.mon, self.mon)
        self.leave(self.cat, self.mon, self.mon, status="pending")
        self.assertEqual(self.cell(self.cal(), self.mon)["off_count"], 1)

    def test_the_agenda_has_only_days_with_something(self):
        self.leave(self.bob, self.mon, self.mon)
        self.assertEqual([d["date"] for d in self.cal()["agenda"]], [self.mon])

    def test_other_workspaces_are_not_shown(self):
        theirs = LeavePolicy.objects.create(company=self.other, name="X")
        LeaveRequest.objects.create(company=self.other, user=self.eve, policy=theirs, start_date=self.mon, end_date=self.mon,
                                    days=Decimal("1"), paid_days=Decimal("1"), unpaid_days=Decimal("0"), status="approved")
        self.assertEqual(self.cell(self.cal(), self.mon)["entries"], [])


class ViewsTest(Base):
    def test_any_member_can_open_the_calendar(self):
        self.leave(self.bob, self.mon, self.mon)
        self.client.login(username="ann", password="pass1234")
        page = self.client.get(reverse("leave:calendar"), {"month": "2030-06"})
        self.assertContains(page, "June 2030")
        self.assertContains(page, "Bob")
        self.assertNotContains(page, "Casual")  # the type is for approvers

    def test_approvers_see_the_type(self):
        self.leave(self.bob, self.mon, self.mon)
        self.client.login(username="approver", password="pass1234")
        self.assertContains(self.client.get(reverse("leave:calendar"), {"month": "2030-06"}), "Casual")

    def test_a_bad_month_falls_back_to_this_one(self):
        self.client.login(username="ann", password="pass1234")
        for bad in ("nope", "2030-13", "99999-01", "2030-6-1"):
            self.assertEqual(self.client.get(reverse("leave:calendar"), {"month": bad}).status_code, 200, bad)

    def test_december_rolls_into_january(self):
        self.client.login(username="ann", password="pass1234")
        page = self.client.get(reverse("leave:calendar"), {"month": "2030-12"})
        self.assertContains(page, "?month=2031-01")

    def test_signed_out_visitors_are_sent_away(self):
        self.assertNotEqual(self.client.get(reverse("leave:calendar")).status_code, 200)

    def test_a_new_request_tells_approvers_and_mentions_clashes(self):
        self.leave(self.bob, self.mon, self.mon)
        self.client.login(username="ann", password="pass1234")
        self.client.post(reverse("leave:apply"), {
            "policy_id": str(self.policy.pk), "start_date": self.mon.isoformat(), "end_date": self.mon.isoformat(), "reason": "trip",
        })
        told = Notification.objects.filter(kind="leave_request")
        self.assertEqual({n.user.username for n in told}, {"owner", "approver"})
        self.assertIn("Bob is also off", told[0].body)

    def test_a_decision_tells_the_applicant(self):
        leave = self.leave(self.ann, self.mon, self.mon, status="pending")
        self.client.login(username="owner", password="pass1234")
        self.client.post(reverse("leave:decision", args=[leave.pk, "reject"]), {
            "start_date": leave.start_date.isoformat(), "end_date": leave.end_date.isoformat(),
            "split_mode": "auto", "note": "busy week",
        })
        n = Notification.objects.get(user=self.ann, kind="leave_decision")
        self.assertIn("rejected", n.title)
        self.assertEqual(n.body, "busy week")

    def test_the_approvals_screen_warns_about_clashes(self):
        self.leave(self.bob, self.mon, self.mon)
        self.leave(self.ann, self.mon, self.mon, status="pending")
        self.client.login(username="owner", password="pass1234")
        page = self.client.get(reverse("leave:approvals"))
        self.assertContains(page, "1 also off")
        self.assertContains(page, "Bob is also off")  # in the dialog payload

    def test_the_applicant_preview_mentions_who_is_already_off(self):
        self.leave(self.bob, self.mon, self.mon)
        self.client.login(username="ann", password="pass1234")
        page = self.client.post(reverse("leave:split_preview"), {
            "policy_id": self.policy.pk, "start_date": self.mon.isoformat(), "end_date": self.mon.isoformat(),
        })
        self.assertContains(page, "Bob is also off")

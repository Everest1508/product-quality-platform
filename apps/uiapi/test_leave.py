from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.test import Client

from apps.dashboards.models import ActivityLog
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.leave.tests import LeaveTestBase
from apps.notifications.models import Notification
from apps.payroll.models import Holiday


class L(LeaveTestBase):
    """Shares the leave world: owner, manager (admin), approver (flagged developer), emp, outsider; Casual (12/yr, 3 per spell), Unpaid."""

    def login(self, name, company=None):
        self.client.login(username=name, password="pass1234")
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = (company or self.company).pk
        s.save()

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")

    def apply_body(self, start=None, end=None, **over):
        start = start or self.monday()
        return {"policy_id": str(self.casual.pk), "start_date": start.isoformat(), "end_date": (end or start).isoformat(), "reason": "trip", **over}

    def decision(self, leave, action="approve", **over):
        body = {"start_date": leave.start_date.isoformat(), "end_date": leave.end_date.isoformat(), "split_mode": "auto", "note": "", **over}
        return self.post(f"/ui-api/v1/leave/requests/{leave.pk}/{action}/", body)


class ApplyApiTest(L):
    def test_members_and_viewers_can_apply_and_approvers_are_told_with_clashes(self):
        viewer = LeaveTestBase.__dict__  # noqa: F841  (the base has no viewer; make one)
        from apps.leave.tests import make_user

        v = make_user("viewer", self.company, "viewer")
        self.login("emp")
        r = self.post("/ui-api/v1/leave/apply/", self.apply_body())
        self.assertEqual((r.status_code, r.json()["message"]), (201, "Leave request submitted for approval."))
        leave = LeaveRequest.objects.get()
        self.assertEqual((leave.user, leave.status, leave.split_mode, leave.days), (self.emp, "pending", "auto", Decimal("1.0")))
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_requested", actor=self.emp).exists())
        self.assertTrue(Notification.objects.filter(user=self.approver, kind=Notification.Kind.LEAVE_REQUEST).exists())
        self.assertFalse(Notification.objects.filter(user=self.emp, kind=Notification.Kind.LEAVE_REQUEST).exists())
        self.login("viewer")
        self.assertEqual(self.post("/ui-api/v1/leave/apply/", self.apply_body(self.monday(1))).status_code, 201)
        assert v

    def test_the_approvers_are_told_who_else_is_off(self):
        self.make_request(user=self.approver, start=self.monday(), status="approved")
        self.login("emp")
        self.post("/ui-api/v1/leave/apply/", self.apply_body())
        told = Notification.objects.filter(kind=Notification.Kind.LEAVE_REQUEST)
        self.assertEqual({n.user.username for n in told}, {"owner", "manager", "approver"})
        self.assertIn("approver is also off", told[0].body)

    def test_an_over_cap_application_is_taken_and_split(self):
        self.login("emp")
        start = self.monday()
        r = self.post("/ui-api/v1/leave/apply/", self.apply_body(start, start + timedelta(days=4)))  # 5 days vs a 3-day paid spell
        self.assertEqual(r.status_code, 201)
        leave = LeaveRequest.objects.get()
        self.assertEqual((leave.paid_days, leave.unpaid_days), (Decimal("3.0"), Decimal("2.0")))

    def test_validation_foreign_policy_past_and_blank(self):
        foreign = LeavePolicy.objects.create(company=self.other, name="Casual", max_days_per_year=Decimal("5.0"))
        self.login("emp")
        self.assertIn("policy_id", self.post("/ui-api/v1/leave/apply/", self.apply_body(policy_id=str(foreign.pk))).json()["errors"])
        past = self.monday() - timedelta(days=30)
        self.assertEqual(self.post("/ui-api/v1/leave/apply/", self.apply_body(past)).status_code, 400)
        self.assertEqual(self.post("/ui-api/v1/leave/apply/", {}).status_code, 400)
        self.assertEqual(self.post("/ui-api/v1/leave/apply/", [1]).status_code, 400)
        self.assertFalse(LeaveRequest.objects.exists())

    def test_the_form_state_lists_this_companys_policies_and_my_balances(self):
        self.login("emp")
        d = self.client.get("/ui-api/v1/leave/apply/").json()
        self.assertEqual(sorted(p["name"] for p in d["policies"]), ["Casual", "Unpaid"])
        self.assertEqual({b["policy"]["name"] for b in d["balances"]}, {"Casual", "Unpaid"})


class PreviewApiTest(L):
    def preview(self, **body):
        return self.post("/ui-api/v1/leave/preview/", body)

    def body(self, start, end=None, **over):
        return {"policy_id": str(self.casual.pk), "start_date": start.isoformat(), "end_date": (end or start).isoformat(), **over}

    def test_it_prices_an_over_cap_spell_before_it_is_submitted(self):
        self.login("emp")
        start = self.monday()
        p = self.preview(**self.body(start, start + timedelta(days=4))).json()["preview"]
        self.assertEqual((p["paid"], p["unpaid"], p["days"]), ("3.0", "2.0", "5.0"))
        self.assertTrue(p["reasons"])

    def test_a_half_day_is_one_half_paid_day(self):
        self.login("emp")
        p = self.preview(**self.body(self.monday(), is_half_day=True)).json()["preview"]
        self.assertEqual((p["days"], p["paid"], p["unpaid"]), ("0.5", "0.5", "0.0"))

    def test_nothing_to_price_is_an_empty_preview_never_an_error(self):
        self.login("emp")
        start = self.monday()
        saturday = start + timedelta(days=5)
        for body in ({}, {"policy_id": str(self.casual.pk)}, self.body(start, start - timedelta(days=2)), self.body(saturday, saturday + timedelta(days=1)),
                     {"policy_id": "x", "start_date": start.isoformat()}, {"policy_id": str(self.casual.pk), "start_date": "garbage"}):
            r = self.preview(**body)
            self.assertEqual((r.status_code, r.json()["preview"]), (200, None), body)

    def test_another_companys_policy_cannot_be_priced_and_others_leave_does_not_lower_mine(self):
        foreign = LeavePolicy.objects.create(company=self.other, name="Casual", max_days_per_year=Decimal("5.0"))
        self.login("emp")
        self.assertIsNone(self.preview(**self.body(self.monday(), policy_id=str(foreign.pk))).json()["preview"])
        start = self.monday()
        self.make_request(user=self.approver, start=start, end=start + timedelta(days=2), days=Decimal("3.0"), status="approved", paid=Decimal("3.0"), unpaid=Decimal("0.0"))
        p = self.preview(**self.body(start, start + timedelta(days=2))).json()["preview"]
        self.assertEqual(p["paid"], "3.0")  # my allowance, not theirs
        self.assertIn("also off", p["clash_text"])
        self.assertEqual(p["clash_people"], ["approver"])

    def test_the_preview_agrees_with_what_is_stored_and_needs_a_login(self):
        self.login("emp")
        start = self.monday()
        end = start + timedelta(days=4)
        p = self.preview(**self.body(start, end)).json()["preview"]
        self.post("/ui-api/v1/leave/apply/", self.apply_body(start, end))
        leave = LeaveRequest.objects.get()
        self.assertEqual((str(leave.paid_days), str(leave.unpaid_days)), (p["paid"], p["unpaid"]))
        self.assertIn(Client().post("/ui-api/v1/leave/preview/", {}, content_type="application/json").status_code, (401, 403))


class MyLeaveAndCancelApiTest(L):
    def test_only_my_requests_and_a_balance_for_each_policy(self):
        mine = self.make_request(user=self.emp)
        self.make_request(user=self.approver)
        self.login("emp")
        d = self.client.get("/ui-api/v1/leave/me/").json()
        self.assertEqual([r["id"] for r in d["requests"]], [mine.pk])
        self.assertEqual({b["policy"]["name"] for b in d["balances"]}, {"Casual", "Unpaid"})
        self.assertEqual((d["can_approve"], d["requests"][0]["can_cancel"]), (False, True))

    def test_no_policies_still_answers(self):
        LeavePolicy.objects.filter(company=self.company).delete()
        self.login("emp")
        self.assertEqual(self.client.get("/ui-api/v1/leave/me/").json()["balances"], [])

    def test_year_param_and_balances_use_clean_numbers(self):
        self.login("emp")
        d = self.client.get("/ui-api/v1/leave/me/", {"year": "2030"}).json()
        self.assertEqual(d["year"], 2030)
        self.assertEqual(self.client.get("/ui-api/v1/leave/me/", {"year": "abc"}).status_code, 200)
        casual = next(b for b in d["balances"] if b["policy"]["name"] == "Casual")
        self.assertEqual((casual["remaining_label"], casual["limit_label"]), ("12", "12"))
        self.assertNotIn("0000", str(d))

    def test_withdraw_own_pending_only(self):
        pending, approved, theirs = self.make_request(user=self.emp), self.make_request(user=self.emp, status="approved"), self.make_request(user=self.approver)
        self.login("emp")
        self.assertEqual(self.post(f"/ui-api/v1/leave/requests/{pending.pk}/cancel/").status_code, 200)
        pending.refresh_from_db()
        self.assertEqual((pending.status, pending.decided_by), ("cancelled", self.emp))
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_cancelled").exists())
        self.assertEqual(self.post(f"/ui-api/v1/leave/requests/{approved.pk}/cancel/").status_code, 400)
        self.assertEqual(self.post(f"/ui-api/v1/leave/requests/{theirs.pk}/cancel/").status_code, 404)


class QueueAndDecisionApiTest(L):
    def test_only_approvers_open_the_queue_or_decide(self):
        leave = self.make_request()
        self.login("emp")
        self.assertEqual(self.client.get("/ui-api/v1/leave/approvals/").status_code, 403)
        self.assertEqual(self.decision(leave).status_code, 403)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")
        for who in ("approver", "owner", "manager"):
            self.login(who)
            self.assertEqual(self.client.get("/ui-api/v1/leave/approvals/").status_code, 200, who)

    def test_the_queue_has_tabs_clashes_and_the_automatic_split_for_pending_rows_only(self):
        start = self.monday()
        pending = self.make_request(start=start, end=start + timedelta(days=4), days=Decimal("5.0"))
        self.make_request(user=self.approver, start=start, end=start, status="approved")
        self.login("approver")
        d = self.client.get("/ui-api/v1/leave/approvals/").json()
        self.assertEqual({t["value"]: t["count"] for t in d["tabs"]}["pending"], 1)
        item = d["items"][0]
        self.assertEqual((item["id"], item["person"]["username"], item["auto_paid"], item["auto_unpaid"]), (pending.pk, "emp", "3.0", "2.0"))
        self.assertIn("also off", item["clash_text"])
        approved = self.client.get("/ui-api/v1/leave/approvals/", {"status": "approved"}).json()
        self.assertNotIn("auto_paid", approved["items"][0])  # only pending rows are actionable
        self.assertEqual(self.client.get("/ui-api/v1/leave/approvals/", {"status": "junk"}).json()["status"], "pending")

    def test_the_queue_only_shows_this_company(self):
        self.make_request()
        LeaveRequest.objects.create(company=self.other, user=self.outsider, policy=LeavePolicy.objects.create(company=self.other, name="Casual", max_days_per_year=Decimal("5.0")),
                                    start_date=self.monday(), end_date=self.monday(), days=Decimal("1.0"))
        self.login("approver")
        self.assertEqual(len(self.client.get("/ui-api/v1/leave/approvals/").json()["items"]), 1)

    def test_approval_is_paid_by_default_logged_and_tells_the_applicant(self):
        start = self.monday()
        leave = self.make_request(start=start, end=start + timedelta(days=1), days=Decimal("2.0"))
        self.login("approver")
        r = self.decision(leave)
        self.assertEqual(r.status_code, 200)
        self.assertIn("approved — 2 paid of 2 days", r.json()["message"])
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.decided_by, leave.paid_days, leave.unpaid_days), ("approved", self.approver, Decimal("2.0"), Decimal("0.0")))
        self.assertIsNotNone(leave.decided_at)
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_approved").exists())
        self.assertTrue(Notification.objects.filter(user=self.emp, kind=Notification.Kind.LEAVE_DECISION).exists())

    def test_a_rejection_tells_the_applicant_with_the_note(self):
        leave = self.make_request()
        self.login("owner")
        self.decision(leave, "reject", note="busy week")
        n = Notification.objects.get(user=self.emp, kind=Notification.Kind.LEAVE_DECISION)
        self.assertIn("rejected", n.title)
        self.assertEqual(n.body, "busy week")

    def test_the_approver_can_overrule_the_split(self):
        start = self.monday()
        leave = self.make_request(start=start, end=start + timedelta(days=1), days=Decimal("2.0"))
        self.login("approver")
        self.decision(leave, split_mode="manual", paid_days="1", unpaid_days="1")
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.paid_days, leave.unpaid_days, leave.split_mode), ("approved", Decimal("1.0"), Decimal("1.0"), "manual"))

    def test_a_manual_split_must_add_up_and_cannot_invent_days(self):
        start = self.monday()
        leave = self.make_request(start=start, end=start + timedelta(days=1), days=Decimal("2.0"))
        self.login("approver")
        for paid, unpaid in (("2", "2"), ("9", "0")):
            r = self.decision(leave, split_mode="manual", paid_days=paid, unpaid_days=unpaid)
            self.assertEqual(r.status_code, 400, (paid, unpaid))
            self.assertTrue(r.json()["detail"])
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.paid_days), ("pending", None))

    def test_the_approver_can_correct_the_dates_and_the_charge_follows(self):
        leave = self.make_request(days=Decimal("1.0"))
        self.login("approver")
        wednesday = leave.start_date + timedelta(days=2)
        self.decision(leave, end_date=wednesday.isoformat())
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.end_date, leave.days, leave.paid_days, leave.unpaid_days), ("approved", wednesday, Decimal("3.0"), Decimal("3.0"), Decimal("0.0")))

    def test_a_decision_without_dates_is_refused(self):
        leave = self.make_request()
        self.login("approver")
        self.assertEqual(self.post(f"/ui-api/v1/leave/requests/{leave.pk}/approve/").status_code, 400)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "pending")

    def test_a_rejection_takes_a_note_and_records_no_split(self):
        leave = self.make_request(days=Decimal("3.0"))
        self.login("approver")
        r = self.decision(leave, "reject", note="Too busy")
        self.assertIn("rejected", r.json()["message"])
        leave.refresh_from_db()
        self.assertEqual((leave.status, leave.decision_note, leave.paid_days, leave.unpaid_days), ("rejected", "Too busy", None, None))
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_rejected").exists())

    def test_cannot_decide_twice_unknown_actions_or_another_companys_request(self):
        done = self.make_request(status="approved")
        pending = self.make_request()
        foreign = LeaveRequest.objects.create(company=self.other, user=self.outsider, policy=LeavePolicy.objects.create(company=self.other, name="Casual", max_days_per_year=Decimal("5.0")),
                                              start_date=self.monday(), end_date=self.monday(), days=Decimal("1.0"))
        self.login("approver")
        self.assertEqual(self.decision(done, "reject").status_code, 400)
        done.refresh_from_db()
        self.assertEqual(done.status, "approved")
        self.assertEqual(self.decision(pending, "burn").status_code, 403)
        self.assertEqual(self.decision(foreign).status_code, 404)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "pending")


class CalendarApiTest(L):
    def cal(self, **p):
        return self.client.get("/ui-api/v1/leave/calendar/", p)

    def test_any_member_opens_it_types_only_for_approvers_and_other_companies_never_show(self):
        start = self.monday()
        self.make_request(user=self.approver, start=start, end=start + timedelta(days=1), days=Decimal("2.0"), status="approved")
        LeaveRequest.objects.create(company=self.other, user=self.outsider, policy=LeavePolicy.objects.create(company=self.other, name="Secret", max_days_per_year=None),
                                    start_date=start, end_date=start, days=Decimal("1.0"), status="approved")
        self.login("emp")
        d = self.cal(month=start.strftime("%Y-%m")).json()
        entries = [e for w in d["weeks"] for day in w for e in day["entries"]]
        self.assertTrue(entries)
        self.assertTrue(all(e["policy"] == "" for e in entries))
        self.assertNotIn("outsider", str(d))
        self.login("approver")
        d = self.cal(month=start.strftime("%Y-%m")).json()
        self.assertTrue(d["show_types"])
        self.assertIn("Casual", {e["policy"] for w in d["weeks"] for day in w for e in day["entries"]})
        self.assertIn(self.client.get("/ui-api/v1/leave/calendar/").status_code, (200,))
        self.assertIn(Client().get("/ui-api/v1/leave/calendar/").status_code, (401, 403))

    def test_weeks_start_on_monday_pending_is_marked_and_rejected_is_hidden(self):
        start = self.monday()
        self.make_request(user=self.emp, start=start, status="pending")
        self.make_request(user=self.approver, start=start, status="rejected")
        self.login("emp")
        d = self.cal(month=start.strftime("%Y-%m")).json()
        self.assertTrue(all(len(w) == 7 for w in d["weeks"]))
        self.assertEqual(d["weeks"][0][0]["is_weekend"], False)
        day = next(x for w in d["weeks"] for x in w if x["date"] == start.isoformat())
        self.assertEqual([(e["name"], e["status"]) for e in day["entries"]], [("emp", "pending")])
        self.assertEqual(day["off_count"], 0)  # pending is a wish, not an absence

    def test_a_holiday_is_named_and_hides_leave_that_day_and_months_roll_over(self):
        start = self.monday()
        Holiday.objects.create(company=self.company, date=start, name="Founders Day")
        self.make_request(user=self.emp, start=start, status="approved")
        self.login("emp")
        d = self.cal(month=start.strftime("%Y-%m")).json()
        day = next(x for w in d["weeks"] for x in w if x["date"] == start.isoformat())
        self.assertEqual((day["holiday"], day["entries"]), ("Founders Day", []))
        self.assertEqual(self.cal(month="2026-12").json()["next"], "2027-01")
        self.assertEqual(self.cal(month="2026-01").json()["prev"], "2025-12")
        self.assertTrue(self.cal(month="junk").json()["is_current"])


class PolicyApiTest(L):
    def body(self, **over):
        return {"name": "Sick", "max_days_per_year": "8", "max_consecutive_days": "", "is_paid": True, "color": "green", "icon": "", **over}

    def test_only_admins_see_add_or_edit(self):
        self.login("emp")
        self.assertEqual(self.client.get("/ui-api/v1/leave/policies/").status_code, 403)
        self.assertEqual(self.post("/ui-api/v1/leave/policies/", self.body()).status_code, 403)
        self.assertEqual(self.client.patch(f"/ui-api/v1/leave/policies/{self.casual.pk}/", self.body(), content_type="application/json").status_code, 403)
        self.login("approver")  # a leave approver is not an admin
        self.assertEqual(self.client.get("/ui-api/v1/leave/policies/").status_code, 403)
        self.login("manager")
        d = self.client.get("/ui-api/v1/leave/policies/").json()
        self.assertEqual(sorted(p["name"] for p in d["policies"]), ["Casual", "Unpaid"])
        self.assertIn(["green", "Green"], d["colors"])
        self.assertTrue(d["icons"])

    def test_add_defaults_unlimited_and_is_logged(self):
        self.login("owner")
        r = self.post("/ui-api/v1/leave/policies/", self.body(max_days_per_year="", color=""))
        self.assertEqual((r.status_code, r.json()["message"]), (201, "Sick leave type added."))
        p = LeavePolicy.objects.get(name="Sick")
        self.assertEqual((p.company, p.max_days_per_year, p.max_consecutive_days), (self.company, None, None))
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_policy_created").exists())
        self.assertEqual(self.post("/ui-api/v1/leave/policies/", self.body()).status_code, 400)  # the name is taken

    def test_edit_blank_means_unlimited_and_the_closed_sets_hold(self):
        self.login("owner")
        url = f"/ui-api/v1/leave/policies/{self.casual.pk}/"
        patch = lambda **o: self.client.patch(url, self.body(name="Casual", **o), content_type="application/json")
        r = patch(max_days_per_year="", color="blue", icon="")
        self.assertEqual(r.status_code, 200)
        self.casual.refresh_from_db()
        self.assertEqual((self.casual.max_days_per_year, self.casual.color), (None, "blue"))
        self.assertIn("color", patch(color="javascript:alert(1)").json()["errors"])
        self.assertIn("icon", patch(icon="not-an-icon").json()["errors"])
        self.assertEqual(patch(color="").status_code, 200)  # blank colour is allowed
        self.assertTrue(ActivityLog.objects.filter(event_type="leave_policy_updated").exists())

    def test_a_spell_cap_above_the_annual_allowance_is_refused_below_is_fine(self):
        self.login("owner")
        r = self.post("/ui-api/v1/leave/policies/", self.body(max_days_per_year="5", max_consecutive_days="8"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("max_consecutive_days", r.json()["errors"])
        self.assertEqual(self.post("/ui-api/v1/leave/policies/", self.body(name="Other", max_days_per_year="10", max_consecutive_days="3")).status_code, 201)

    def test_another_companys_policy_is_404(self):
        foreign = LeavePolicy.objects.create(company=self.other, name="X", max_days_per_year=None)
        self.login("owner")
        self.assertEqual(self.client.patch(f"/ui-api/v1/leave/policies/{foreign.pk}/", self.body(name="X"), content_type="application/json").status_code, 404)

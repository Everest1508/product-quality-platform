"""Odd input must answer 400/404, never 500, and never leave a half-saved write behind."""
from datetime import timedelta

from apps.accounts.models import Membership
from apps.leave.models import LeaveRequest
from apps.products.models import APIKey, Product
from apps.uiapi import test_attendance as att
from apps.uiapi import test_leave as lv
from apps.uiapi import test_payroll as pay
from apps.uiapi import test_products_pages as prod


class ProductInputTest(prod.P):
    def setUp(self):
        super().setUp()
        self.login("owner")

    def test_bad_milestones_do_not_save_the_product_then_crash(self):
        before = Product.objects.count()
        for bad in ("oops", [1, "x", None], {"a": 1}):
            r = self.post("/ui-api/v1/products/", {"name": f"Probe {abs(hash(str(bad)))}", "default_environment": "production", "milestones": bad})
            self.assertLess(r.status_code, 500, bad)
        self.assertEqual(Product.objects.count(), before + 3)  # each saved once, none half-saved by a crash

    def test_milestone_key_and_rotate_inputs(self):
        url = f"/ui-api/v1/products/{self.p_open.pk}/"
        self.assertEqual(self.post(url + "milestones/", {"title": 5, "target_date": "2026-01-01"}).status_code, 400)
        self.assertLess(self.post(url + "milestones/", {"title": "x", "target_date": "2026-01-01", "order": "9" * 25}).status_code, 500)
        self.assertEqual(self.post(url + "milestones/", {"title": "x", "target_date": "2026-01-01", "order": [1]}).status_code, 400)
        self.assertEqual(self.post(url + "api-keys/", {"name": 5}).status_code, 200)
        key = APIKey.objects.get()
        self.assertEqual(self.post(f"/ui-api/v1/api-keys/{key.pk}/rotate/", {"grace": ["1d"]}).status_code, 400)


class AttendanceInputTest(att.Base):
    def test_correction_fields_of_the_wrong_type_are_refused(self):
        self.login("dev")
        url = "/ui-api/v1/attendance/corrections/request/"
        day = (self.today - timedelta(days=1)).isoformat()
        for body in ({"date": 20260101, "reason": "x"}, {"date": day, "check_in": 9, "reason": "x"}, {"date": day, "check_in": "09:00", "reason": 5}):
            self.assertLess(self.post(url, body).status_code, 500, body)

    def test_record_edit_and_week_survive_odd_input(self):
        rec = self.record()
        self.login("owner")
        self.assertLess(self.client.patch(f"/ui-api/v1/attendance/records/{rec.pk}/", {"check_in": 5}, content_type="application/json").status_code, 500)
        r = self.client.patch(f"/ui-api/v1/attendance/records/{rec.pk}/", {"check_in": "2026-01-01T09:00", "notes": 5}, content_type="application/json")
        self.assertLess(r.status_code, 500)
        self.assertEqual(self.client.get("/ui-api/v1/attendance/team/", {"view": "week", "week": "0001-01-01"}).status_code, 200)


class PayrollInputTest(pay.P):
    def test_bad_ids_and_out_of_range_dates(self):
        self.login("owner")
        self.assertEqual(self.post("profiles/", {"membership": "abc"}).status_code, 404)
        self.assertEqual(self.get("preview/", anchor="9999-12-28").status_code, 200)
        self.assertEqual(self.post("preview/", {"anchor": "0001-01-05"}).status_code, 200)


class LeaveRulesTest(lv.L):
    def test_a_request_whose_start_has_passed_can_still_be_rejected(self):
        past = self.make_request(start=self.monday() - timedelta(days=60))
        self.login("approver")
        r = self.decision(past, "reject", note="too late")
        self.assertEqual(r.status_code, 200)
        past.refresh_from_db()
        self.assertEqual((past.status, past.decision_note), ("rejected", "too late"))

    def test_an_approver_cannot_decide_their_own_request_unless_they_are_the_only_one(self):
        mine = self.make_request(user=self.approver)
        self.login("approver")
        self.assertEqual(self.decision(mine).status_code, 400)
        mine.refresh_from_db()
        self.assertEqual(mine.status, "pending")
        Membership.objects.filter(company=self.company, role__in=["owner", "admin"]).update(role="viewer")
        Membership.objects.filter(user=self.owner).update(role="viewer")
        Membership.objects.filter(user=self.approver).update(is_leave_approver=True)
        self.assertEqual(self.decision(mine).status_code, 200)
        self.assertEqual(LeaveRequest.objects.get(pk=mine.pk).status, "approved")

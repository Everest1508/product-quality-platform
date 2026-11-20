from decimal import Decimal as D

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.costing import service
from apps.costing.models import Estimate

SHEET = {
    "dedicated_days": "45", "hours_per_month": "240", "hours_per_day": "8",
    "rent_monthly": "8000", "ai_per_person_month": "2000", "margin_percent": "50",
    "people": [
        {"name": "M1", "salary": "20000", "time": "80", "unit": "hours"},
        {"name": "D1", "salary": "10000", "time": "20", "unit": "days"},
    ],
    "others": [{"name": "Misc", "amount": "3000"}],
}


class ComputeTest(TestCase):
    def test_sheet_numbers(self):
        r = service.compute(SHEET)
        self.assertEqual(r["people"][0]["rate"], D("83.33"))
        self.assertEqual(r["people"][0]["cost"], D("6666.67"))
        self.assertEqual(r["people"][1]["hours"], D("160"))  # 20 days x 8
        self.assertEqual(r["people"][1]["cost"], D("6666.67"))
        self.assertEqual(r["months"], D("1.5"))
        self.assertEqual(r["rent"], D("12000.00"))
        self.assertEqual(r["ai"], D("6000.00"))  # 2 people x 2000 x 1.5
        self.assertEqual(r["total"], D("34333.33"))
        self.assertEqual(r["price"], D("51500.00"))  # x1.5

    def test_true_margin_and_pitch(self):
        r = service.compute({**SHEET, "margin_mode": "margin", "pitch_price": "60000"})
        self.assertEqual(r["price"], D("68666.67"))  # cost / 0.5
        self.assertEqual(r["pitch_profit"], D("25666.67"))

    def test_blank_and_junk_never_crash(self):
        r = service.compute({"hours_per_month": "0", "people": [{"name": "x", "salary": "abc", "time": "5"}], "margin_mode": "margin", "margin_percent": "150"})
        self.assertEqual(r["total"], D("0.00"))

    def test_inr_grouping(self):
        self.assertEqual(service.inr(D("1234567")), "₹12,34,567")
        self.assertEqual(service.inr(D("42236.5")), "₹42,236.50")
        self.assertEqual(service.inr(D("-5")), "-₹5")

    def test_quoted_and_actual_prices_show_the_difference(self):
        r = service.compute({**SHEET, "pitch_price": "40000", "actual_price": "38000"})
        self.assertEqual(r["quoted"], D("40000.00"))
        self.assertEqual(r["actual"], D("38000.00"))
        self.assertEqual(r["actual_minus_quoted"], D("-2000.00"))
        self.assertEqual(r["actual_profit"], D("3666.67"))
        self.assertEqual(r["shown_profit"], r["actual_profit"])
        self.assertEqual(r["quoted_vs_price"], D("-11500.00"))
        blank = service.compute(SHEET)
        self.assertFalse(blank["has_actual"])
        self.assertEqual(blank["quoted"], blank["price"])


class AccessTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.users = {}
        for role in ("owner", "admin", "developer", "viewer"):
            u = User.objects.create_user(role, password="x")
            Membership.objects.create(user=u, company=self.co, role=role)
            self.users[role] = u
        self.est = Estimate.objects.create(company=self.co, name="Aestheti", **{k: v for k, v in SHEET.items() if k in ("people", "others")})

    def office(self, inputs):
        hpm, hpd = service.office_hours(self.co)
        return service.compute({**inputs, "hours_per_month": hpm, "hours_per_day": hpd})

    def test_office_hours_come_from_attendance_settings(self):
        # 10:00-18:30 less 30 min = 8h a day; a month is 30 days
        self.assertEqual(service.office_hours(self.co), (D("240.00"), D("8.00")))

    def login(self, role):
        self.client.force_login(self.users[role])
        s = self.client.session
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.co.pk
        s.save()

    def test_only_owner_and_admin(self):
        urls = [reverse("costing:estimate_list"), reverse("costing:estimate_new"), reverse("costing:estimate_edit", args=[self.est.pk]), reverse("costing:estimate_detail", args=[self.est.pk]),
                reverse("costing:estimate_quote", args=[self.est.pk])]
        for role in ("developer", "viewer"):
            self.login(role)
            for u in urls:
                self.assertEqual(self.client.get(u).status_code, 403, (role, u))
            self.assertEqual(self.client.post(reverse("costing:estimate_calc"), {}).status_code, 403)
        for role in ("owner", "admin"):
            self.login(role)
            for u in urls:
                self.assertEqual(self.client.get(u).status_code, 200, (role, u))

    def test_other_company_estimate_is_404(self):
        other = Company.objects.create(name="O", slug="o")
        e = Estimate.objects.create(company=other, name="Secret")
        self.login("owner")
        self.assertEqual(self.client.get(reverse("costing:estimate_edit", args=[e.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("costing:estimate_delete", args=[e.pk])).status_code, 404)

    def test_save_and_quote_hides_internal_numbers(self):
        self.login("admin")
        import json
        r = self.client.post(reverse("costing:estimate_new"), {
            "name": "Proj", "client_name": "Cl", "dedicated_days": "45", "client_days": "60",
            "rent_monthly": "8000",
            "ai_per_person_month": "2000", "margin_percent": "50", "margin_mode": "markup", "pitch_price": "",
            "people_json": json.dumps(SHEET["people"]), "others_json": json.dumps(SHEET["others"]),
        })
        self.assertEqual(r.status_code, 302)
        e = Estimate.objects.get(name="Proj")
        page = self.client.get(reverse("costing:estimate_quote", args=[e.pk])).content.decode()
        r = self.office(SHEET)
        self.assertIn(service.inr(r["price"]), page)
        self.assertNotIn("20000", page)
        self.assertNotIn(service.inr(r["total"]), page)  # internal cost
        self.assertIn("Total quotation", page)
        lines, price = service.quote_lines(r)
        self.assertEqual(sum(l["amount"] for l in lines), price)  # lines add up to the total
        self.assertEqual(lines[0]["label"], "M1")

    def test_calc_returns_total(self):
        self.login("owner")
        import json
        r = self.client.post(reverse("costing:estimate_calc"), {
            "dedicated_days": "45",
            "rent_monthly": "8000", "ai_per_person_month": "2000", "margin_percent": "50",
            "people_json": json.dumps(SHEET["people"]), "others_json": json.dumps(SHEET["others"]),
        })
        self.assertContains(r, service.inr(self.office(SHEET)["total"]))


class DealTest(AccessTest):
    def save(self, **extra):
        import json
        data = {
            "name": "Won project", "client_name": "Zed", "dedicated_days": "45", "client_days": "60",
            "rent_monthly": "8000", "ai_per_person_month": "2000", "margin_percent": "50",
            "margin_mode": "markup", "pitch_price": "40000", "actual_price": "38000",
            "people_json": json.dumps(SHEET["people"]), "others_json": json.dumps(SHEET["others"]),
            **extra,
        }
        r = self.client.post(reverse("costing:estimate_new"), data)
        self.assertEqual(r.status_code, 302)
        return Estimate.objects.get(name=data["name"])

    def test_actual_price_is_saved_and_compared(self):
        self.login("owner")
        e = self.save()
        self.assertEqual(e.actual_price, "38000")
        detail = self.client.get(reverse("costing:estimate_detail", args=[e.pk])).content.decode()
        self.assertIn("Actually got the project for", detail)
        self.assertIn("Actual − quoted price", detail)
        self.assertIn(service.inr(D("-2000")), detail)
        listing = self.client.get(reverse("costing:estimate_list")).content.decode()
        self.assertIn("Quoted price", listing)
        self.assertIn("Actual price", listing)
        self.assertIn(service.inr(D("38000")), listing)
        self.assertIn(service.inr(D("-2000")), listing)

    def test_live_calc_shows_the_comparison(self):
        self.login("owner")
        import json
        r = self.client.post(reverse("costing:estimate_calc"), {
            "dedicated_days": "45", "rent_monthly": "8000", "ai_per_person_month": "2000",
            "margin_percent": "50", "pitch_price": "40000", "actual_price": "38000",
            "people_json": json.dumps(SHEET["people"]), "others_json": json.dumps(SHEET["others"]),
        })
        self.assertContains(r, "Actually got the project for")
        self.assertContains(r, service.inr(D("-2000")))
        self.assertContains(r, service.inr(D("3666.67")))

    def test_actual_price_never_reaches_the_client_quote(self):
        self.login("owner")
        e = self.save()
        page = self.client.get(reverse("costing:estimate_quote", args=[e.pk])).content.decode()
        self.assertNotIn(service.inr(D("38000")), page)
        self.assertNotIn("actually got", page.lower())
        self.assertIn(service.inr(D("40000")), page)

    def test_unwanted_reports_are_gone(self):
        self.login("owner")
        page = self.client.get(reverse("costing:estimate_list")).content.decode()
        self.assertIn("Won project" if Estimate.objects.filter(name="Won project").exists() else "Aestheti", page)
        for gone in ("By client", "Export CSV", 'name="month"', "co-stats", "Gross margin"):
            self.assertNotIn(gone, page)
        from django.urls.exceptions import NoReverseMatch
        with self.assertRaises(NoReverseMatch):
            reverse("costing:estimate_export")

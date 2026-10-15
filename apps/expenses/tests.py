from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.expenses import service
from apps.expenses.models import Expense


class MoneyFormatTest(TestCase):
    def test_money_format_uses_indian_grouping(self):
        self.assertEqual(service.format_paise(123456700), "₹12,34,567")
        self.assertEqual(service.format_paise(12345), "₹123.45")
        self.assertEqual(service.format_paise(5), "₹0.05")


class ExpenseViewsTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        mk = lambda n, role: (User.objects.create_user(n, password="x"), role)
        self.owner, _ = mk("owner", "owner")
        self.dev, _ = mk("dev", "developer")
        self.dev2, _ = mk("dev2", "developer")
        self.viewer, _ = mk("viewer", "viewer")
        for u, r in [(self.owner, "owner"), (self.dev, "developer"), (self.dev2, "developer"), (self.viewer, "viewer")]:
            Membership.objects.create(user=u, company=self.co, role=r)
        self.other_co = Company.objects.create(name="Other", slug="other")

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        from django.conf import settings
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.co.pk
        s.save()

    def add(self, user, amount="300", payer=None):
        self.login(user)
        return self.client.post(reverse("expenses:expense_list"), {
            "amount": amount, "paid_by": (payer or user).pk, "date": "2026-10-14",
            "category": "tea", "note": "",
        })

    def test_add_stores_paise_and_shows_totals(self):
        self.assertEqual(self.add(self.owner, "1250.50", payer=self.dev).status_code, 302)
        e = Expense.objects.get()
        self.assertEqual((e.amount_paise, e.company, e.paid_by), (125050, self.co, self.dev))
        page = self.client.get(reverse("expenses:expense_list"))
        self.assertContains(page, "Tea")
        self.assertEqual(page.context["total"], "₹1,250.50")
        self.assertEqual(page.context["by_person"], [{"name": "dev", "total": "₹1,250.50"}])

    def test_amount_accepts_the_commas_the_box_adds(self):
        self.add(self.owner, "12,34,567.50")
        self.assertEqual(Expense.objects.get().amount_paise, 123456750)

    def test_needs_a_positive_amount_and_a_real_payer(self):
        self.add(self.owner, amount="0")
        self.add(self.owner, payer=self.viewer)
        self.assertEqual(Expense.objects.count(), 0)

    def test_other_needs_a_typed_kind_and_other_categories_drop_it(self):
        post = lambda **kw: self.client.post(reverse("expenses:expense_list"), {
            "amount": "5", "paid_by": self.owner.pk, "date": "2026-10-14", "note": "", **kw})
        self.login(self.owner)
        post(category="other", category_other="")
        self.assertEqual(Expense.objects.count(), 0)
        post(category="other", category_other="Printer ink")
        post(category="tea", category_other="ignored")
        a, b = Expense.objects.order_by("id")
        self.assertEqual((a.category_label, b.category_label, b.category_other), ("Printer ink", "Tea", ""))

    def test_filters_and_csv_export(self):
        self.add(self.owner, "100")
        self.client.post(reverse("expenses:expense_list"), {
            "amount": "250", "paid_by": self.dev.pk, "date": "2026-09-02", "category": "other",
            "category_other": "Printer ink", "note": "=cmd()"})
        url = reverse("expenses:expense_list")
        self.assertEqual(self.client.get(url + "?month=all").context["count"], 2)
        self.assertEqual(self.client.get(url + "?month=2026-09").context["count"], 1)
        self.assertEqual(self.client.get(url + "?month=all&category=tea").context["count"], 1)
        self.assertEqual(self.client.get(url + f"?month=all&paid_by={self.dev.pk}").context["count"], 1)
        self.assertEqual(self.client.get(url + "?month=all&q=printer").context["count"], 1)
        ctx = self.client.get(url + "?month=all").context
        self.assertEqual({c["name"] for c in ctx["by_category"]}, {"Tea", "Printer ink"})
        out = self.client.get(reverse("expenses:expense_export") + "?month=all")
        body = out.content.decode()
        self.assertIn("text/csv", out["Content-Type"])
        self.assertIn("'=cmd()", body)
        self.assertIn(",Total,350.00,", body)
        self.client.force_login(self.dev)
        self.assertEqual(self.client.get(reverse("expenses:expense_export")).status_code, 403)

    def test_empty_page_says_so_and_offers_add(self):
        self.login(self.owner)
        page = self.client.get(reverse("expenses:expense_list"))
        self.assertContains(page, "No expenses added yet")
        self.assertContains(page, 'id="ex-dlg"')
        self.assertNotContains(page, "Paid by")

    def test_only_owners_and_admins_can_see_or_use_it(self):
        self.add(self.owner)
        e = Expense.objects.get()
        for user in (self.dev, self.viewer):
            self.login(user)
            self.assertEqual(self.client.get(reverse("expenses:expense_list")).status_code, 403)
            self.assertEqual(self.client.post(reverse("expenses:expense_list"), {}).status_code, 403)
            self.assertEqual(self.client.get(reverse("expenses:expense_edit", args=[e.pk])).status_code, 403)
            self.assertEqual(self.client.post(reverse("expenses:expense_delete", args=[e.pk])).status_code, 403)

    def test_an_admin_can_edit_and_delete(self):
        self.add(self.owner)
        e = Expense.objects.get()
        self.client.post(reverse("expenses:expense_edit", args=[e.pk]), {
            "amount": "10", "paid_by": self.owner.pk, "date": "2026-10-15", "category": "ai", "note": "",
        })
        e.refresh_from_db()
        self.assertEqual((e.category, e.amount_paise), ("ai", 1000))
        self.client.post(reverse("expenses:expense_delete", args=[e.pk]))
        self.assertEqual(Expense.objects.count(), 0)

    def test_another_company_cannot_open_it(self):
        self.add(self.owner)
        e = Expense.objects.get()
        out = User.objects.create_user("out", password="x")
        Membership.objects.create(user=out, company=self.other_co, role="owner")
        self.client.force_login(out)
        s = self.client.session
        from django.conf import settings
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.other_co.pk
        s.save()
        self.assertEqual(self.client.get(reverse("expenses:expense_edit", args=[e.pk])).status_code, 404)

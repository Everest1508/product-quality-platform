from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.expenses import service
from apps.expenses.models import Expense


class SplitMathTest(TestCase):
    def test_shares_always_add_up(self):
        s = service.shares(10000, [3, 1, 2])
        self.assertEqual(sum(s.values()), 10000)
        self.assertEqual(sorted(s.values()), [3333, 3333, 3334])

    def test_money_format_uses_indian_grouping(self):
        self.assertEqual(service.format_paise(123456700), "₹12,34,567")
        self.assertEqual(service.format_paise(12345), "₹123.45")
        self.assertEqual(service.format_paise(5), "₹0.05")

    def test_settlements_clear_every_balance(self):
        net = {1: 7000, 2: -3000, 3: -4000}
        pay = service.settlements(net)
        got = {u: 0 for u in net}
        for a, b, p in pay:
            got[a] += p
            got[b] -= p
        self.assertEqual({u: -v for u, v in got.items()}, net)
        self.assertLessEqual(len(pay), 2)


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

    def add(self, user, amount="300", payer=None, split=None):
        self.login(user)
        return self.client.post(reverse("expenses:expense_list"), {
            "title": "Lunch", "amount": amount, "paid_by": (payer or user).pk, "date": "2026-10-14",
            "category": "food", "split_with": [u.pk for u in (split or [self.owner, self.dev, self.dev2])], "note": "",
        })

    def test_add_stores_paise_and_shows_balances(self):
        self.assertEqual(self.add(self.dev).status_code, 302)
        e = Expense.objects.get()
        self.assertEqual(e.amount_paise, 30000)
        self.assertEqual(e.company, self.co)
        page = self.client.get(reverse("expenses:expense_list"))
        self.assertContains(page, "Lunch")
        self.assertEqual(page.context["my_state"], "owed")
        self.assertEqual(page.context["my_balance"], "₹200")

    def test_needs_at_least_one_person_and_a_positive_amount(self):
        self.add(self.dev, amount="0", split=[])
        self.assertEqual(Expense.objects.count(), 0)

    def test_cannot_pay_or_share_with_a_viewer_or_outsider(self):
        self.add(self.dev, split=[self.viewer])
        self.assertEqual(Expense.objects.count(), 0)

    def test_viewers_are_blocked(self):
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse("expenses:expense_list")).status_code, 403)

    def test_only_creator_or_admin_can_change_and_only_admin_can_settle(self):
        self.add(self.dev)
        e = Expense.objects.get()
        self.login(self.dev2)
        self.assertEqual(self.client.get(reverse("expenses:expense_edit", args=[e.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("expenses:expense_delete", args=[e.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("expenses:expense_settle")).status_code, 403)
        self.login(self.dev)
        self.assertEqual(self.client.get(reverse("expenses:expense_edit", args=[e.pk])).status_code, 200)
        self.login(self.owner)
        self.client.post(reverse("expenses:expense_settle"))
        e.refresh_from_db()
        self.assertIsNotNone(e.settled_at)
        self.assertEqual(self.client.get(reverse("expenses:expense_list")).context["open_count"], 0)

    def test_another_company_cannot_open_it(self):
        self.add(self.dev)
        e = Expense.objects.get()
        out = User.objects.create_user("out", password="x")
        Membership.objects.create(user=out, company=self.other_co, role="owner")
        self.client.force_login(out)
        s = self.client.session
        from django.conf import settings
        s[settings.ACTIVE_COMPANY_SESSION_KEY] = self.other_co.pk
        s.save()
        self.assertEqual(self.client.get(reverse("expenses:expense_edit", args=[e.pk])).status_code, 404)

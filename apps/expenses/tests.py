from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.dashboards.models import ActivityLog
from apps.expenses import service
from apps.expenses.models import Expense, ExpenseComment
from apps.notifications.models import Notification


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
        self.assertEqual(page.context["by_person"], [{"pk": self.dev.pk, "name": "dev", "total": "₹1,250.50", "can_add": True}])

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


class ExpenseDiscussionTest(TestCase):
    """A small thread on each expense, for the people who can open the ledger."""

    def setUp(self):
        from django.conf import settings

        self.settings = settings
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.other_co = Company.objects.create(name="Other", slug="other")
        self.owner = User.objects.create_user("owner", password="x", first_name="Olive", last_name="Owner")
        self.admin = User.objects.create_user("admin", password="x")
        self.dev = User.objects.create_user("dev", password="x")
        for user, role in ((self.owner, "owner"), (self.admin, "admin"), (self.dev, "developer")):
            Membership.objects.create(user=user, company=self.co, role=role)
        self.expense = Expense.objects.create(
            company=self.co, amount_paise=30000, date=date(2026, 10, 14), category="tea",
            paid_by=self.owner, created_by=self.owner,
        )
        self.url = reverse("expenses:expense_comment", args=[self.expense.pk])
        self.page = reverse("expenses:expense_edit", args=[self.expense.pk])

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        s[self.settings.ACTIVE_COMPANY_SESSION_KEY] = self.co.pk
        s.save()

    def say(self, user, text="Was this the October bill?"):
        self.login(user)
        return self.client.post(self.url, {"body": text})

    def test_a_comment_is_saved_shown_and_lands_back_on_the_thread(self):
        res = self.say(self.owner)
        self.assertRedirects(res, self.page + "#discussion", fetch_redirect_response=False)
        c = ExpenseComment.objects.get()
        self.assertEqual((c.expense, c.author, c.company, c.body), (self.expense, self.owner, self.co, "Was this the October bill?"))
        page = self.client.get(self.page)
        self.assertContains(page, "Discussion")
        self.assertContains(page, "Olive Owner")
        self.assertContains(page, "Was this the October bill?")

    def test_the_toast_arrives_with_the_page_after_the_redirect(self):
        self.login(self.owner)
        res = self.client.post(self.url, {"body": "hello"}, follow=True)
        self.assertContains(res, 'id="toast-seed"')
        self.assertContains(res, "Comment added.")

    def test_the_other_owners_and_admins_are_told_but_not_the_author_or_a_developer(self):
        self.say(self.owner, "Please check the amount")
        told = Notification.objects.filter(kind="comment")
        self.assertEqual([n.user for n in told], [self.admin])
        n = told.get()
        self.assertEqual(n.url, f"/expenses/{self.expense.pk}/#discussion")
        self.assertIn("Olive Owner commented on Tea (₹300)", n.title)
        self.assertEqual(n.body, "Please check the amount")
        self.assertEqual(n.actor, self.owner)

    def test_a_blank_or_huge_comment_is_refused_with_a_reason(self):
        self.login(self.owner)
        for text, message in (("   ", "Write something before you send it."), ("x" * 2001, "Keep a comment under 2,000 characters.")):
            with self.subTest(len=len(text)):
                res = self.client.post(self.url, {"body": text}, follow=True)
                self.assertContains(res, message)
        self.assertEqual(ExpenseComment.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_the_comment_is_shown_as_text_never_as_markup(self):
        self.say(self.owner, "<script>alert(1)</script>")
        page = self.client.get(self.page)
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_only_owners_and_admins_can_read_or_write_in_it(self):
        self.say(self.owner)
        self.login(self.dev)
        self.assertEqual(self.client.get(self.page).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"body": "hi"}).status_code, 403)
        c = ExpenseComment.objects.get()
        delete = reverse("expenses:expense_comment_delete", args=[self.expense.pk, c.pk])
        self.assertEqual(self.client.post(delete).status_code, 403)
        self.assertEqual(ExpenseComment.objects.count(), 1)

    def test_you_can_delete_your_own_comment_and_only_yours(self):
        self.say(self.owner, "mine")
        self.say(self.admin, "theirs")
        mine, theirs = ExpenseComment.objects.order_by("id")
        delete = lambda c: reverse("expenses:expense_comment_delete", args=[self.expense.pk, c.pk])

        self.login(self.owner)
        self.assertEqual(self.client.post(delete(theirs)).status_code, 403)  # not even an owner
        self.assertEqual(ExpenseComment.objects.count(), 2)
        res = self.client.post(delete(mine), follow=True)
        self.assertContains(res, "Comment deleted.")
        self.assertEqual(list(ExpenseComment.objects.all()), [theirs])
        # The delete button is only drawn on your own comments, and it asks first. The
        # confirm box needs a title in `data-confirm`; a bare attribute never asks.
        self.say(self.owner, "again")
        page = self.client.get(self.page)
        self.assertNotContains(page, delete(theirs))
        self.assertContains(page, 'data-confirm="Delete your comment?"')

    def test_a_comment_cannot_be_reached_through_another_expense_or_company(self):
        self.say(self.owner)
        c = ExpenseComment.objects.get()
        other = Expense.objects.create(
            company=self.co, amount_paise=100, date=date(2026, 10, 14), category="tea",
            paid_by=self.owner, created_by=self.owner,
        )
        self.assertEqual(
            self.client.post(reverse("expenses:expense_comment_delete", args=[other.pk, c.pk])).status_code, 404
        )
        out = User.objects.create_user("out", password="x")
        Membership.objects.create(user=out, company=self.other_co, role="owner")
        self.client.force_login(out)
        s = self.client.session
        s[self.settings.ACTIVE_COMPANY_SESSION_KEY] = self.other_co.pk
        s.save()
        self.assertEqual(self.client.post(self.url, {"body": "hi"}).status_code, 404)

    def test_the_ledger_shows_how_many_comments_each_expense_has(self):
        listing = lambda: self.client.get(reverse("expenses:expense_list") + "?month=all")
        self.login(self.owner)
        self.assertContains(listing(), "Discuss")
        self.say(self.owner, "one")
        self.say(self.admin, "two")
        self.login(self.owner)
        page = listing()
        self.assertEqual(page.context["rows"][0].comment_count, 2)
        self.assertContains(page, 'title="2 comments"')

    def test_deleting_the_expense_takes_its_thread_with_it(self):
        self.say(self.owner)
        self.client.post(reverse("expenses:expense_delete", args=[self.expense.pk]))
        self.assertEqual(ExpenseComment.objects.count(), 0)

    def test_comments_are_audited(self):
        self.say(self.owner)
        c = ExpenseComment.objects.get()
        self.client.post(reverse("expenses:expense_comment_delete", args=[self.expense.pk, c.pk]))
        kinds = list(ActivityLog.objects.filter(company=self.co).order_by("id").values_list("event_type", flat=True))
        self.assertEqual(kinds, ["expense_commented", "expense_comment_deleted"])
        # The words themselves stay out of the audit trail.
        self.assertFalse(ActivityLog.objects.filter(description__contains="October").exists())


class SalaryAllTest(ExpenseViewsTest):
    # Reuses the base setUp; its own tests are run once, in ExpenseViewsTest.
    def test_adds_only_that_persons_unpaid_expenses(self):
        self.add(self.owner, "100", payer=self.dev)
        self.add(self.owner, "200", payer=self.dev)
        self.add(self.owner, "300", payer=self.dev2)
        r = self.client.post(reverse("expenses:expense_salary_all"), {"paid_by": self.dev.pk, "month": "all"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(list(Expense.objects.filter(to_salary=True).values_list("paid_by", flat=True)), [self.dev.pk] * 2)
        self.assertEqual(self.client.get(reverse("expenses:expense_list") + "?month=all").status_code, 200)


class RepaidDirectlyTest(ExpenseViewsTest):
    def test_direct_and_salary_exclude_each_other(self):
        self.add(self.owner, "100", payer=self.dev)
        e = Expense.objects.get()
        self.client.post(reverse("expenses:expense_salary", args=[e.pk]))
        self.client.post(reverse("expenses:expense_repaid", args=[e.pk]))
        e.refresh_from_db()
        self.assertEqual((e.to_salary, bool(e.repaid_on)), (False, True))
        self.client.post(reverse("expenses:expense_salary", args=[e.pk]))  # refused
        e.refresh_from_db()
        self.assertFalse(e.to_salary)

    def test_bulk_direct_skips_salary_marked(self):
        self.add(self.owner, "100", payer=self.dev)
        self.add(self.owner, "200", payer=self.dev)
        Expense.objects.filter(amount_paise=10000).update(to_salary=True)
        self.client.post(reverse("expenses:expense_salary_all"), {"paid_by": self.dev.pk, "month": "all", "mode": "direct"})
        self.assertEqual(Expense.objects.filter(repaid_on__isnull=False).count(), 1)

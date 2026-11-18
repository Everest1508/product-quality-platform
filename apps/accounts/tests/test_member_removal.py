from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User
from apps.payroll.models import PayrollProfile
from apps.products.models import Product
from apps.tickets.models import Ticket


class RemoveMemberKeepsHistoryTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("own", password="x")
        self.dev = User.objects.create_user("dev", password="x")
        Membership.objects.create(user=self.owner, company=self.co, role="owner")
        self.m = Membership.objects.create(user=self.dev, company=self.co, role="developer")
        self.product = Product.objects.create(company=self.co, name="P", key="PP")

    def _ticket(self, status):
        t = Ticket.objects.create(company=self.co, product=self.product, title=status, status=status)
        t.set_assignees([self.dev])
        return t

    def test_open_unassigned_closed_kept_payroll_off(self):
        open_t, done_t = self._ticket("open"), self._ticket("closed")
        old = PayrollProfile.objects.create(
            company=self.co, user=self.dev, monthly_salary=Decimal("1000"),
            effective_from="2020-01-01", is_on_payroll=True)
        self.client.force_login(self.owner)
        s = self.client.session
        s["active_company_id"] = self.co.pk
        s.save()
        self.client.post(reverse("accounts:team_remove", args=[self.m.pk]))

        self.assertFalse(Membership.objects.filter(pk=self.m.pk).exists())
        open_t.refresh_from_db(); done_t.refresh_from_db()
        self.assertEqual(list(open_t.assignees.all()), [])
        self.assertIsNone(open_t.assigned_to)
        self.assertEqual(open_t.former_assignees, "dev")
        self.assertEqual(done_t.former_assignees, "")
        self.assertEqual(list(done_t.assignees.all()), [self.dev])
        self.assertEqual(done_t.assigned_to, self.dev)
        old.refresh_from_db()
        self.assertTrue(old.is_on_payroll)  # history untouched
        newest = PayrollProfile.objects.filter(user=self.dev).order_by("-effective_from").first()
        self.assertFalse(newest.is_on_payroll)

import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.models import Company, Membership
from apps.products.models import Product
from apps.tickets.models import Ticket

from .registry import REPORTS

User = get_user_model()


class ReportsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.owner = User.objects.create_user("owner", "o@x.com", "pw12345678")
        self.dev = User.objects.create_user("dev", "d@x.com", "pw12345678")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.product = Product.objects.create(company=self.company, name="Alpha", slug="alpha")
        Ticket.objects.create(company=self.company, product=self.product, title="Broken thing", created_by=self.owner)

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def test_every_report_runs_for_owner_and_matches_its_columns(self):
        self.login(self.owner)
        for key, rep in REPORTS.items():
            r = self.client.get(reverse("reports:run", args=[key]))
            self.assertEqual(r.status_code, 200, key)
            res = rep.run(__import__("apps.reports.views", fromlist=["x"]).RunView().context(r.wsgi_request, key)[1])
            for row in res.rows:
                self.assertEqual(len(row), len(res.columns), key)

    def test_reports_are_for_owners_and_admins_only(self):
        self.login(self.dev)
        self.assertEqual(self.client.get(reverse("reports:hub")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:run", args=["ticket-ageing"]) + "?export=xlsx").status_code, 403)

    def test_excel_download_is_named_and_readable(self):
        self.login(self.owner)
        r = self.client.get(reverse("reports:run", args=["ticket-register"]) + "?period=30d&export=xlsx")
        self.assertIn("Acme-Corp_Ticket-register_", r["Content-Disposition"])
        self.assertTrue(r["Content-Disposition"].endswith('.xlsx"'))
        ws = load_workbook(io.BytesIO(r.content))["Ticket register"]
        self.assertEqual(ws["A1"].value, "Ticket")
        self.assertIn("Broken thing", [c.value for c in ws[2]])

    def test_csv_download(self):
        self.login(self.owner)
        r = self.client.get(reverse("reports:run", args=["ticket-ageing"]) + "?export=csv")
        self.assertIn("as-of-", r["Content-Disposition"])
        self.assertIn("Open tickets", r.content.decode("utf-8-sig"))

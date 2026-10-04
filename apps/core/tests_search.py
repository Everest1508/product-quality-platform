from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.ingestion.models import ErrorGroup
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


def make(username, company, role, first="", last=""):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234", first_name=first, last_name=last)
    Membership.objects.create(user=user, company=company, role=role)
    return user


class SearchTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.owner = make("owner", self.company, "owner", "Olive", "Owen")
        self.dev = make("dev", self.company, "developer", "Dana", "Dev")
        self.outsider = make("outsider", self.other, "owner")
        self.open_product = Product.objects.create(name="Billing Portal", slug="billing", company=self.company)
        self.secret_product = Product.objects.create(name="Secret Vault", slug="vault", company=self.company)
        ProductAccess.objects.create(company=self.company, product=self.open_product, user=self.dev)
        self.open_ticket = Ticket.objects.create(company=self.company, product=self.open_product, title="Invoice emails go to spam", created_by=self.owner)
        self.secret_ticket = Ticket.objects.create(company=self.company, product=self.secret_product, title="Invoice vault leak", created_by=self.owner)
        self.foreign_ticket = Ticket.objects.create(
            company=self.other, product=Product.objects.create(name="Billing X", slug="bx", company=self.other),
            title="Invoice elsewhere", created_by=self.outsider,
        )
        self.open_error = ErrorGroup.objects.create(company=self.company, product=self.open_product, fingerprint="a", title="TimeoutError invoice sync")
        self.secret_error = ErrorGroup.objects.create(company=self.company, product=self.secret_product, fingerprint="b", title="TimeoutError vault sync")

    def search(self, user, q):
        self.client.login(username=user, password="pass1234")
        response = self.client.get(reverse("search"), {"q": q})
        self.assertEqual(response.status_code, 200)
        return {g["label"]: g["items"] for g in response.json()["groups"]}

    def titles(self, groups, label):
        return [i["title"] for i in groups.get(label, [])]

    def test_a_member_finds_tickets_they_can_open(self):
        groups = self.search("dev", "invoice")
        self.assertEqual(self.titles(groups, "Tickets"), [f"#{self.open_ticket.pk} Invoice emails go to spam"])

    def test_a_member_never_sees_a_product_they_have_no_access_to(self):
        groups = self.search("dev", "vault")
        self.assertNotIn("Tickets", groups)
        self.assertNotIn("Errors", groups)
        self.assertNotIn("Products", groups)

    def test_owners_see_every_product(self):
        groups = self.search("owner", "invoice")
        self.assertEqual(len(groups["Tickets"]), 2)
        self.assertIn("Secret Vault", self.titles(self.search("owner", "vault"), "Products"))

    def test_other_workspaces_are_invisible(self):
        for user in ("owner", "dev"):
            groups = self.search(user, "elsewhere")
            self.assertNotIn("Tickets", groups)

    def test_error_groups_follow_product_access(self):
        self.assertEqual(self.titles(self.search("dev", "timeout"), "Errors"), ["TimeoutError invoice sync"])
        self.assertEqual(len(self.search("owner", "timeout")["Errors"]), 2)

    def test_a_ticket_number_finds_the_ticket(self):
        for q in (str(self.open_ticket.pk), f"#{self.open_ticket.pk}"):
            groups = self.search("dev", q)
            self.assertIn(self.open_ticket.pk, [int(t["title"].split()[0][1:]) for t in groups["Tickets"]])

    def test_a_ticket_number_does_not_reveal_one_you_cannot_open(self):
        groups = self.search("dev", str(self.secret_ticket.pk))
        self.assertNotIn(f"#{self.secret_ticket.pk} Invoice vault leak", self.titles(groups, "Tickets"))

    def test_results_link_to_real_pages(self):
        item = self.search("dev", "invoice")["Tickets"][0]
        self.assertEqual(item["url"], reverse("tickets:ticket_detail", args=[self.open_ticket.pk]))

    def test_people_are_searchable_by_admins_only(self):
        self.assertEqual(self.titles(self.search("owner", "dana"), "People"), ["Dana Dev"])
        self.assertNotIn("People", self.search("dev", "olive"))

    def test_admin_pages_are_only_offered_to_admins(self):
        self.assertIn("Payroll runs", self.titles(self.search("owner", "payroll"), "Go to"))
        member_pages = self.titles(self.search("dev", "pay"), "Go to")
        self.assertNotIn("Payroll runs", member_pages)
        self.assertNotIn("Payroll setup", member_pages)
        self.assertIn("My payslips", member_pages)

    def test_an_empty_query_offers_pages_to_jump_to(self):
        groups = self.search("dev", "")
        self.assertEqual(list(groups), ["Go to"])
        self.assertIn("All tickets", self.titles(groups, "Go to"))

    def test_a_one_letter_query_does_not_search_records(self):
        self.assertNotIn("Tickets", self.search("owner", "i"))

    def test_results_are_capped(self):
        for i in range(20):
            Ticket.objects.create(company=self.company, product=self.open_product, title=f"Crash {i}", created_by=self.owner)
        self.assertLessEqual(len(self.search("owner", "crash")["Tickets"]), 6)

    def test_wildcards_and_quotes_are_just_text(self):
        for q in ("%", "_", "' OR 1=1 --", "<script>", "\\"):
            self.client.login(username="owner", password="pass1234")
            self.assertEqual(self.client.get(reverse("search"), {"q": q}).status_code, 200)

    def test_signed_out_visitors_get_nothing(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(reverse("search"), {"q": "invoice"}).status_code, 200)

    def test_the_page_carries_the_palette_and_a_search_button(self):
        self.client.login(username="dev", password="pass1234")
        page = self.client.get(reverse("dashboards:index"), follow=True).content.decode()
        self.assertIn('role="combobox"', page)
        self.assertIn("pq-palette", page)

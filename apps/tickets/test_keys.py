from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.products.keys import suggest_key, unique_key
from apps.products.models import Product
from apps.tickets.models import Ticket

User = get_user_model()


class SuggestKeyTest(TestCase):
    def test_first_letters_of_each_part(self):
        self.assertEqual(suggest_key("AU-Marketing"), "AUM")
        self.assertEqual(suggest_key("AU-HRMS"), "AUH")
        self.assertEqual(suggest_key("AU-Marketing-Staging"), "AUMS")

    def test_short_single_word_is_kept(self):
        self.assertEqual(suggest_key("CRM"), "CRM")
        self.assertEqual(suggest_key("Neomed"), "NEO")

    def test_long_first_word_gives_two_letters(self):
        self.assertEqual(suggest_key("Aureole Websites"), "AUW")
        self.assertEqual(suggest_key("POS Eble"), "POSE")

    def test_odd_names_still_give_a_valid_key(self):
        for name in ("", "---", "123 Go", "X", "Ünïcode Shop"):
            key = suggest_key(name)
            self.assertRegex(key, r"^[A-Z][A-Z0-9]{1,5}$", name)

    def test_collisions_get_a_number(self):
        self.assertEqual(unique_key("AU-Marketing", {"AUM"}), "AUM2")
        self.assertEqual(unique_key("AU-Marketing", {"AUM", "AUM2"}), "AUM3")


class TicketNumberTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.other = Company.objects.create(name="Other", slug="other")
        self.p1 = Product.objects.create(company=self.company, name="AU-Marketing", slug="aum")
        self.p2 = Product.objects.create(company=self.company, name="AU-HRMS", slug="auh")

    def make(self, product, title="t"):
        return Ticket.objects.create(company=self.company, product=product, title=title)

    def test_product_gets_a_key_on_creation(self):
        self.assertEqual((self.p1.key, self.p2.key), ("AUM", "AUH"))

    def test_same_name_in_another_company_may_share_a_key(self):
        twin = Product.objects.create(company=self.other, name="AU-Marketing", slug="aum")
        self.assertEqual(twin.key, "AUM")

    def test_two_products_in_one_company_never_share_a_key(self):
        clash = Product.objects.create(company=self.company, name="Au Marketing", slug="au-marketing-2")
        self.assertEqual(clash.key, "AUM2")

    def test_numbers_count_up_per_product(self):
        a, b, c = self.make(self.p1), self.make(self.p1), self.make(self.p2)
        self.assertEqual([a.key, b.key, c.key], ["AUM-001", "AUM-002", "AUH-001"])

    def test_a_deleted_number_is_not_reused(self):
        a, b = self.make(self.p1), self.make(self.p1)
        b.delete()
        self.assertEqual(self.make(self.p1).key, "AUM-003")

    def test_numbers_grow_past_three_digits(self):
        Product.objects.filter(pk=self.p1.pk).update(ticket_counter=999)
        self.assertEqual(self.make(self.p1).key, "AUM-1000")

    def test_saving_again_keeps_the_number(self):
        t = self.make(self.p1)
        t.title = "renamed"
        t.save()
        t.refresh_from_db()
        self.assertEqual(t.key, "AUM-001")

    def test_moving_a_ticket_gives_it_a_number_from_the_new_product(self):
        t = self.make(self.p1)
        self.make(self.p2)
        t = Ticket.objects.get(pk=t.pk)
        t.product = self.p2
        t.save()
        t.refresh_from_db()
        self.assertEqual(t.key, "AUH-002")

    def test_a_ticket_without_a_product_falls_back_to_its_id(self):
        t = Ticket.objects.create(company=self.company, title="loose")
        self.assertIsNone(t.number)
        self.assertEqual(t.key, f"#{t.pk}")

    def test_renaming_the_key_renames_every_ticket(self):
        t = self.make(self.p1)
        Product.objects.filter(pk=self.p1.pk).update(key="MKT")
        t = Ticket.objects.select_related("product").get(pk=t.pk)
        self.assertEqual(t.key, "MKT-001")

    def test_backfill_numbers_old_tickets_in_creation_order(self):
        import importlib

        from django.apps import apps as django_apps

        mig = importlib.import_module("apps.tickets.migrations.0007_backfill_ticket_keys")
        a, b = self.make(self.p1), self.make(self.p1)
        Ticket.objects.update(number=None)
        Product.objects.update(key="", ticket_counter=0)
        mig.backfill(django_apps, None)
        a.refresh_from_db(); b.refresh_from_db(); self.p1.refresh_from_db()
        self.assertEqual((a.number, b.number, self.p1.ticket_counter, self.p1.key), (1, 2, 2, "AUM"))


class TicketKeyScreensTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = User.objects.create_user("own", "o@t.local", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.product = Product.objects.create(company=self.company, name="AU-Marketing", slug="aum")
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Banner is broken", created_by=self.owner)
        self.client.login(username="own", password="pass1234")

    def test_list_board_and_detail_show_the_key(self):
        for url in (reverse("tickets:ticket_list"), reverse("tickets:ticket_board"),
                    reverse("tickets:ticket_detail", args=[self.ticket.pk])):
            self.assertContains(self.client.get(url), "AUM-001")

    def test_creating_a_ticket_reports_its_key(self):
        res = self.client.post(reverse("products:product_ticket_create", args=[self.product.pk]),
                               {"title": "Second", "ticket_type": "bug", "priority": "medium"}, follow=True)
        self.assertContains(res, "Ticket AUM-002 created")

    def test_search_finds_by_key_in_any_spelling(self):
        for q in ("AUM-001", "aum-1", "AUM001", "aum 1"):
            body = self.client.get(reverse("search"), {"q": q}).json()
            titles = [i["title"] for g in body["groups"] for i in g["items"]]
            self.assertIn("AUM-001 Banner is broken", titles, q)

    def test_search_still_finds_the_old_hash_number(self):
        body = self.client.get(reverse("search"), {"q": f"#{self.ticket.pk}"}).json()
        titles = [i["title"] for g in body["groups"] for i in g["items"]]
        self.assertIn("AUM-001 Banner is broken", titles)

    def test_search_by_bare_key_lists_that_products_tickets(self):
        body = self.client.get(reverse("search"), {"q": "AUM"}).json()
        titles = [i["title"] for g in body["groups"] for i in g["items"]]
        self.assertIn("AUM-001 Banner is broken", titles)

    def test_product_form_validates_and_saves_the_key(self):
        other = Product.objects.create(company=self.company, name="Other App", slug="other-app")
        url = reverse("products:product_edit", args=[self.product.pk])
        bad = self.client.post(url, {"name": "AU-Marketing", "key": other.key, "default_environment": "production"})
        self.assertContains(bad, "already uses")
        worse = self.client.post(url, {"name": "AU-Marketing", "key": "1x!", "default_environment": "production"})
        self.assertContains(worse, "starting with a letter")
        ok = self.client.post(url, {"name": "AU-Marketing", "key": "mkt", "default_environment": "production"})
        self.assertEqual(ok.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.key, "MKT")
        self.assertContains(self.client.get(reverse("tickets:ticket_list")), "MKT-001")

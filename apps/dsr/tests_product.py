import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dsr.models import DSREntry
from apps.products.models import Product, ProductAccess
from apps.tickets.models import Ticket

User = get_user_model()


class DSRProductTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="developer")
        self.mine = Product.objects.create(company=self.company, name="Billing", slug="billing")
        self.secret = Product.objects.create(company=self.company, name="Secret Vault", slug="vault")
        ProductAccess.objects.create(company=self.company, product=self.mine, user=self.dev)
        self.client.login(username="dev", password="pass1234")
        self.today = timezone.localdate()

    def add(self, **data):
        payload = {"task_name": "Wrote the report", "category": "other", "status": "completed", "hours_spent": "1.5"}
        payload.update(data)
        return self.client.post(reverse("dsr:dsr_add"), payload, HTTP_HX_REQUEST="true")

    def test_the_form_offers_only_products_the_person_can_open(self):
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertIn("Billing", body)
        self.assertNotIn("Secret Vault", body)

    def test_an_entry_can_be_tagged_with_a_product(self):
        self.add(product=self.mine.pk)
        self.assertEqual(DSREntry.objects.get().product, self.mine)

    def test_product_is_optional(self):
        self.add()
        self.assertIsNone(DSREntry.objects.get().product)

    def test_a_product_the_person_cannot_open_is_refused(self):
        res = self.add(product=self.secret.pk)
        self.assertFalse(DSREntry.objects.exists())
        self.assertNotContains(res, "Secret Vault")

    def test_the_form_is_empty_again_after_a_successful_add(self):
        res = self.add(task_name="Unique text from the first entry")
        body = res.content.decode()
        self.assertEqual(DSREntry.objects.count(), 1)
        # The text is in the list now, but not as a value in the open form.
        composer = body.split('class="dsr-composer"')[1].split("</form>")[0]
        self.assertNotIn("Unique text from the first entry", composer)
        self.assertIn("Unique text from the first entry", body)
        self.assertIn("addOpen: true", body)

    def test_a_failed_add_keeps_what_was_typed_and_shows_why(self):
        res = self.add(task_name="Half finished", hours_spent="0")
        body = res.content.decode()
        self.assertFalse(DSREntry.objects.exists())
        self.assertIn('value="Half finished"', body)
        self.assertIn(">Billing</option>", body)
        self.assertIn("more than zero hours", body)

    def test_a_manual_row_has_a_product_picker_and_saves_a_change(self):
        self.add()
        entry = DSREntry.objects.get()
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertIn('name="product"', body)
        res = self.client.post(
            reverse("dsr:dsr_update", kwargs={"pk": entry.pk}),
            {"task_name": entry.task_name, "product": self.mine.pk, "category": "other", "hours_spent": "1.5", "status": "completed", "notes": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(res.status_code, 200)
        entry.refresh_from_db()
        self.assertEqual(entry.product, self.mine)

    def test_a_row_cannot_be_moved_to_a_product_the_person_cannot_open(self):
        self.add(product=self.mine.pk)
        entry = DSREntry.objects.get()
        self.client.post(
            reverse("dsr:dsr_update", kwargs={"pk": entry.pk}),
            {"task_name": entry.task_name, "product": self.secret.pk, "category": "other", "hours_spent": "1.5", "status": "completed", "notes": ""},
            HTTP_HX_REQUEST="true",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.product, self.mine)

    def test_a_row_edit_that_sends_no_product_keeps_the_product(self):
        self.add(product=self.mine.pk)
        entry = DSREntry.objects.get()
        self.client.post(
            reverse("dsr:dsr_update", kwargs={"pk": entry.pk}),
            {"hours_spent": "2"},
            HTTP_HX_REQUEST="true",
        )
        entry.refresh_from_db()
        self.assertEqual((entry.product, str(entry.hours_spent)), (self.mine, "2.00"))

    def test_the_copied_summary_names_the_product(self):
        self.add(product=self.mine.pk)
        res = self.client.get(reverse("dsr:dsr_sheet"))
        self.assertIn("[Billing] Wrote the report", res.context["copy_summary_text"])


class DSRProductFromTicketsTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.dev = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.dev, company=self.company, role="owner")
        self.product = Product.objects.create(company=self.company, name="Billing", slug="billing")
        self.ticket = Ticket.objects.create(company=self.company, product=self.product, title="Fix it", created_by=self.dev)
        self.ticket.set_assignees([self.dev])

    def test_an_auto_logged_entry_takes_the_tickets_product(self):
        self.ticket.transition_to("resolved", actor=self.dev)
        self.assertEqual(DSREntry.objects.get().product, self.product)

    def test_backfill_gives_old_ticket_entries_a_product(self):
        entry = DSREntry.objects.create(company=self.company, user=self.dev, ticket=self.ticket, task_name="old", hours_spent=1)
        self.assertIsNone(entry.product)
        mig = importlib.import_module("apps.dsr.migrations.0004_backfill_entry_product")
        mig.backfill(django_apps, None)
        entry.refresh_from_db()
        self.assertEqual(entry.product, self.product)

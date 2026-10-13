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

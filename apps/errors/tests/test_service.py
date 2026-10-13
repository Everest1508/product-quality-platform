from django.test import TestCase

from apps.accounts.models import Company, Membership
from apps.dashboards.models import ActivityLog
from apps.errors import service
from apps.ingestion.models import ErrorGroup
from apps.products.models import Product
from django.contrib.auth import get_user_model


class ErrorServiceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = get_user_model().objects.create_user("owner", "o@t.local", "pass1234")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        self.product = Product.objects.create(company=self.company, name="App", slug="app")
        self.group = ErrorGroup.objects.create(
            company=self.company, product=self.product, fingerprint="f", title="Boom", severity="critical",
        )

    def test_resolve_and_ignore_keep_their_events(self):
        self.assertIsNone(service.set_status(self.group, "resolved", self.owner, self.company))
        self.assertIsNone(service.set_status(self.group, "ignored", self.owner, self.company))
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, "ignored")
        self.assertTrue(ActivityLog.objects.filter(event_type="error_resolved").exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="error_ignored").exists())

    def test_other_moves_log_from_and_to(self):
        service.set_status(self.group, "investigating", self.owner, self.company)
        row = ActivityLog.objects.get(event_type="error_status_changed")
        self.assertEqual((row.metadata["from"], row.metadata["to"]), ("open", "investigating"))

    def test_unknown_status_changes_nothing(self):
        self.assertIn("not a valid", service.set_status(self.group, "bogus", self.owner, self.company))
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, "open")
        self.assertFalse(ActivityLog.objects.exists())

    def test_convert_links_the_ticket_and_sets_priority(self):
        t = service.convert_to_ticket(self.group, self.owner, self.company)
        self.assertEqual((t.linked_error_group, t.priority, t.ticket_type), (self.group, "high", "bug"))
        self.assertTrue(ActivityLog.objects.filter(event_type="ticket_created").exists())

    def test_delete_logs(self):
        pk = service.delete_error(self.group, self.owner, self.company)
        self.assertFalse(ErrorGroup.objects.filter(pk=pk).exists())
        self.assertTrue(ActivityLog.objects.filter(event_type="error_deleted").exists())

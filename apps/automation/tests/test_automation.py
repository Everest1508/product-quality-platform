from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.automation.models import AutoTicketLog, AutoTicketRule
from apps.ingestion.models import ErrorGroup
from apps.products.models import Product
from apps.tickets.models import Ticket

User = get_user_model()


class EvaluateRulesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)

    def test_threshold_creates_ticket(self):
        rule = AutoTicketRule.objects.create(
            company=self.company,
            product=self.product,
            name="High error rate",
            trigger_type="error_threshold",
            threshold_count=5,
            window_minutes=60,
            action="create_ticket",
            assign_to=self.user,
        )
        eg = ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Critical error", severity="critical",
            occurrence_count=10,
        )

        call_command("evaluate_rules")

        rule.refresh_from_db()
        self.assertEqual(rule.trigger_count, 1)
        self.assertIsNotNone(rule.last_triggered_at)

        ticket = Ticket.objects.first()
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.source, "auto")
        self.assertEqual(ticket.linked_error_group, eg)
        self.assertEqual(ticket.assigned_to, self.user)
        self.assertIn("Critical error", ticket.title)

    def test_threshold_not_met(self):
        AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="High threshold", trigger_type="error_threshold",
            threshold_count=100, window_minutes=60, action="create_ticket",
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Error", occurrence_count=5,
        )

        call_command("evaluate_rules")
        self.assertEqual(Ticket.objects.count(), 0)

    def test_notify_only_action(self):
        rule = AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="Notify only", trigger_type="error_threshold",
            threshold_count=5, window_minutes=60, action="notify_only",
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Error", occurrence_count=10,
        )

        call_command("evaluate_rules")
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(AutoTicketLog.objects.count(), 1)
        log = AutoTicketLog.objects.first()
        self.assertEqual(log.action_taken, "notify_only")

    def test_no_duplicate_triggers(self):
        AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="Rule", trigger_type="error_threshold",
            threshold_count=5, window_minutes=60, action="create_ticket",
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Error", occurrence_count=10,
        )

        call_command("evaluate_rules")
        call_command("evaluate_rules")
        self.assertEqual(Ticket.objects.count(), 1)

    def test_dry_run(self):
        AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="Rule", trigger_type="error_threshold",
            threshold_count=5, window_minutes=60, action="create_ticket",
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Error", occurrence_count=10,
        )

        call_command("evaluate_rules", dry_run=True)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(AutoTicketLog.objects.count(), 0)

    def test_disabled_rule_skipped(self):
        AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="Disabled", trigger_type="error_threshold",
            threshold_count=5, window_minutes=60, action="create_ticket",
            is_active=False,
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="abc", title="Error", occurrence_count=10,
        )

        call_command("evaluate_rules")
        self.assertEqual(Ticket.objects.count(), 0)

    def test_severity_filter(self):
        rule = AutoTicketRule.objects.create(
            company=self.company, product=self.product,
            name="Critical only", trigger_type="error_threshold",
            threshold_count=5, window_minutes=60, action="create_ticket",
            severity="critical",
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="low", title="Low error", severity="low",
            occurrence_count=10,
        )
        ErrorGroup.objects.create(
            product=self.product, company=self.company,
            fingerprint="crit", title="Critical error", severity="critical",
            occurrence_count=10,
        )

        call_command("evaluate_rules")
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertIn("Critical error", Ticket.objects.first().title)


class RuleViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_rule_list(self):
        response = self.client.get(reverse("automation:rule_list"))
        self.assertEqual(response.status_code, 200)

    def test_create_rule(self):
        response = self.client.post(reverse("automation:rule_create"), {
            "name": "Test Rule",
            "trigger_type": "error_threshold",
            "threshold_count": 10,
            "window_minutes": 60,
            "action": "create_ticket",
            "is_active": True,
            "product": self.product.pk,
            "severity": "",
            "assign_to": "",
        })
        self.assertRedirects(response, reverse("automation:rule_list"))
        self.assertEqual(AutoTicketRule.objects.count(), 1)
        rule = AutoTicketRule.objects.first()
        self.assertEqual(rule.company, self.company)

    def test_toggle_rule(self):
        rule = AutoTicketRule.objects.create(
            company=self.company, name="Toggle", is_active=True,
        )
        response = self.client.post(reverse("automation:rule_toggle", kwargs={"pk": rule.pk}))
        rule.refresh_from_db()
        self.assertFalse(rule.is_active)

    def test_delete_rule(self):
        rule = AutoTicketRule.objects.create(
            company=self.company, name="Delete me",
        )
        response = self.client.post(reverse("automation:rule_delete", kwargs={"pk": rule.pk}))
        self.assertFalse(AutoTicketRule.objects.filter(pk=rule.pk).exists())

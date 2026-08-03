import json
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import Company, Membership
from apps.products.models import Product
from apps.products.webhook import _mention, notify_ticket_created
from apps.tickets.models import Ticket


class WebhookMentionTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.product = Product.objects.create(
            name="App",
            slug="app",
            company=self.company,
            discord_webhook_url="https://discord.com/api/webhooks/abc/xyz",
        )

    def _user(self, username, discord_id=""):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.create_user(username, f"{username}@test.com", "pass1234", discord_id=discord_id)

    def test_mention_formats_discord_id(self):
        user = self._user("alice", discord_id="123456789012345678")
        self.assertEqual(_mention(user), "<@123456789012345678>")

    def test_mention_none_without_discord_id(self):
        user = self._user("bob")
        self.assertIsNone(_mention(user))

    @patch("apps.products.webhook.send_discord_webhook")
    def test_notify_ticket_created_mentions_assignee(self, mock_send):
        assignee = self._user("alice", discord_id="123456789012345678")
        ticket = Ticket.objects.create(
            company=self.company,
            product=self.product,
            title="Help",
            ticket_type="bug",
            priority="high",
            created_by=self._user("creator"),
            assigned_to=assignee,
        )
        notify_ticket_created(ticket)
        self.assertTrue(mock_send.called)
        args, kwargs = mock_send.call_args
        self.assertEqual(args[0], self.product.discord_webhook_url)
        self.assertIn("<@123456789012345678>", kwargs["content"])

    @patch("apps.products.webhook.send_discord_webhook")
    def test_notify_ticket_created_no_mention_without_discord_id(self, mock_send):
        assignee = self._user("bob")
        ticket = Ticket.objects.create(
            company=self.company,
            product=self.product,
            title="Help",
            ticket_type="bug",
            priority="high",
            assigned_to=assignee,
        )
        notify_ticket_created(ticket)
        self.assertTrue(mock_send.called)
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs["content"], "")

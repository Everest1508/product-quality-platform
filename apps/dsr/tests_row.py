from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.dsr.models import DSREntry

User = get_user_model()


class DSRLogRowTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.user = User.objects.create_user("dev", "d@t.local", "pass1234")
        Membership.objects.create(user=self.user, company=self.company, role="developer")
        self.client.login(username="dev", password="pass1234")
        today = timezone.localdate()
        self.a = DSREntry.objects.create(company=self.company, user=self.user, date=today, task_name="Plan", category="meeting", hours_spent=1, status="in_progress", is_auto_logged=False)
        self.b = DSREntry.objects.create(company=self.company, user=self.user, date=today, task_name="Fix", category="bug_fix", hours_spent=2, status="completed", is_auto_logged=False)

    def test_each_row_is_its_own_form(self):
        """Radios with one name and no form are a single group on the page, so a
        choice in one row used to clear the others."""
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertEqual(body.count('<form id="dsr-row-'), 2)
        self.assertIn(f'id="dsr-row-{self.a.pk}"', body)

    def test_manual_rows_are_not_tagged_auto(self):
        body = self.client.get(reverse("dsr:dsr_sheet")).content.decode()
        self.assertNotIn('class="dsr-tag auto"', body)

    def test_inline_edit_returns_a_row_that_is_still_editable(self):
        res = self.client.post(
            reverse("dsr:dsr_update", kwargs={"pk": self.a.pk}),
            {"task_name": "Plan sprint", "category": "meeting", "hours_spent": "1.5", "status": "blocked", "notes": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(res.status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual((self.a.task_name, str(self.a.hours_spent), self.a.status), ("Plan sprint", "1.50", "blocked"))
        body = res.content.decode()
        self.assertIn('name="hours_spent"', body)
        self.assertIn("hx-post", body)

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership, User
from apps.attendance.models import AttendanceRecord


class AddMissingDayTest(TestCase):
    def setUp(self):
        self.co = Company.objects.create(name="Acme", slug="acme")
        self.owner = self._user("owner", "owner")
        self.dev = self._user("dev", "developer")
        self.day = timezone.localdate() - timedelta(days=3)
        self.url = reverse("attendance:attendance_add", args=[self.dev.pk, self.day])

    def _user(self, name, role):
        u = User.objects.create_user(name, f"{name}@t.local", "pass1234")
        Membership.objects.create(user=u, company=self.co, role=role)
        return u

    def post(self, user, **extra):
        self.client.force_login(user)
        data = {"check_in": f"{self.day}T10:00", "check_out": f"{self.day}T18:30", "notes": "forgot"}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_admin_adds_a_day_and_it_is_marked_edited(self):
        self.post(self.owner)
        rec = AttendanceRecord.objects.get(user=self.dev, date=self.day)
        self.assertTrue(rec.is_edited)
        self.assertEqual(rec.notes, "forgot")

    def test_reason_and_check_in_are_required(self):
        self.post(self.owner, notes="")
        self.post(self.owner, check_in="")
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_non_admin_cannot_add(self):
        self.assertEqual(self.post(self.dev).status_code, 403)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_existing_day_goes_to_edit_and_future_is_404(self):
        self.post(self.owner)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        future = reverse("attendance:attendance_add", args=[self.dev.pk, timezone.localdate() + timedelta(days=2)])
        self.assertEqual(self.client.get(future).status_code, 404)

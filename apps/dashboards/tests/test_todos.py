from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Membership, User

from apps.dashboards.models import Todo


class TodoTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme")
        self.me = User.objects.create_user("me", password="x")
        self.other = User.objects.create_user("other", password="x")
        for u in (self.me, self.other):
            Membership.objects.create(user=u, company=self.company, role="viewer")
        self.client.force_login(self.me)
        s = self.client.session
        s["active_company_id"] = self.company.pk
        s.save()

    def test_add_toggle_delete_and_privacy(self):
        self.client.post(reverse("dashboards:todos"), {"text": "ship it"})
        t = Todo.objects.get(user=self.me)
        theirs = Todo.objects.create(user=self.other, text="secret")
        self.assertEqual(self.client.post(reverse("dashboards:todo_toggle", args=[theirs.pk])).status_code, 404)
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))
        t.refresh_from_db()
        self.assertTrue(t.done)
        self.assertNotContains(self.client.get(reverse("dashboards:todos")), "secret")
        self.client.post(reverse("dashboards:todo_delete", args=[t.pk]))
        self.assertFalse(Todo.objects.filter(pk=t.pk).exists())

    def test_due_date_and_clear_done(self):
        self.client.post(reverse("dashboards:todos"), {"text": "a", "due": "2026-10-12"})
        self.client.post(reverse("dashboards:todos"), {"text": "b", "due": "garbage"})
        a = Todo.objects.get(text="a")
        self.assertEqual(str(a.due), "2026-10-12")
        self.assertIsNone(Todo.objects.get(text="b").due)
        self.client.post(reverse("dashboards:todo_toggle", args=[a.pk]))
        self.client.post(reverse("dashboards:todo_clear_done"))
        self.assertEqual(list(Todo.objects.filter(user=self.me).values_list("text", flat=True)), ["b"])

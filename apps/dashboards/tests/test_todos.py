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

    def test_priority_is_saved_and_bad_value_falls_back(self):
        self.client.post(reverse("dashboards:todos"), {"text": "hi", "priority": "3"})
        self.client.post(reverse("dashboards:todos"), {"text": "other", "priority": "9"})
        self.assertEqual(Todo.objects.get(text="hi").priority, Todo.Priority.HIGH)
        self.assertEqual(Todo.objects.get(text="other").priority, Todo.Priority.MEDIUM)

    def test_finishing_a_todo_adds_it_to_todays_dsr_and_undoing_removes_it(self):
        from django.utils import timezone

        from apps.dsr.models import DSREntry

        self.client.post(reverse("dashboards:todos"), {"text": "write report"})
        t = Todo.objects.get(text="write report")
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))  # undo
        self.assertFalse(DSREntry.objects.filter(user=self.me).exists())
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))  # done again
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))  # undo
        self.client.post(reverse("dashboards:todo_toggle", args=[t.pk]))  # done
        rows = DSREntry.objects.filter(user=self.me, source="todo")
        self.assertEqual(rows.count(), 1)  # toggling never duplicates
        self.assertEqual((rows[0].task_name, rows[0].date), ("write report", timezone.localdate()))

    def test_overdue_reminder_goes_out_once_a_day(self):
        from datetime import timedelta

        from django.core.management import call_command
        from django.utils import timezone

        from apps.notifications.models import Notification

        Todo.objects.create(user=self.me, company=self.company, text="late", due=timezone.localdate() - timedelta(days=1))
        Todo.objects.create(user=self.other, company=self.company, text="fine", due=timezone.localdate())
        call_command("notify_todos")
        call_command("notify_todos")
        self.assertEqual(Notification.objects.filter(user=self.me, title="You have overdue to-dos").count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.other).exists())

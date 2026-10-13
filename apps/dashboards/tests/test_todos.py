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

    def post(self, url, body=None):
        return self.client.post(url, body or {}, content_type="application/json")

    def test_add_toggle_delete_and_privacy(self):
        r = self.post("/ui-api/v1/todos/", {"text": "ship it"})
        self.assertEqual(r.status_code, 201)
        t = Todo.objects.get(user=self.me)
        theirs = Todo.objects.create(user=self.other, text="secret")
        self.assertEqual(self.post(f"/ui-api/v1/todos/{theirs.pk}/toggle/").status_code, 404)
        self.assertEqual(self.client.delete(f"/ui-api/v1/todos/{theirs.pk}/").status_code, 404)
        self.post(f"/ui-api/v1/todos/{t.pk}/toggle/")
        t.refresh_from_db()
        self.assertTrue(t.done)
        self.assertNotIn("secret", self.client.get("/ui-api/v1/todos/").content.decode())
        self.client.delete(f"/ui-api/v1/todos/{t.pk}/")
        self.assertFalse(Todo.objects.filter(pk=t.pk).exists())

    def test_due_date_and_clear_done(self):
        self.post("/ui-api/v1/todos/", {"text": "a", "due": "2026-10-12"})
        self.post("/ui-api/v1/todos/", {"text": "b", "due": "garbage"})
        a = Todo.objects.get(text="a")
        self.assertEqual(str(a.due), "2026-10-12")
        self.assertIsNone(Todo.objects.get(text="b").due)
        self.post(f"/ui-api/v1/todos/{a.pk}/toggle/")
        self.post("/ui-api/v1/todos/clear-done/")
        self.assertEqual(list(Todo.objects.filter(user=self.me).values_list("text", flat=True)), ["b"])

    def test_priority_is_saved_and_bad_value_falls_back(self):
        self.post("/ui-api/v1/todos/", {"text": "hi", "priority": "3"})
        self.post("/ui-api/v1/todos/", {"text": "other", "priority": "9"})
        self.assertEqual(Todo.objects.get(text="hi").priority, Todo.Priority.HIGH)
        self.assertEqual(Todo.objects.get(text="other").priority, Todo.Priority.MEDIUM)

    def test_finishing_a_todo_adds_it_to_todays_dsr_and_undoing_removes_it(self):
        from django.utils import timezone

        from apps.dsr.models import DSREntry

        self.post("/ui-api/v1/todos/", {"text": "write report"})
        t = Todo.objects.get(text="write report")
        toggle = lambda: self.post(f"/ui-api/v1/todos/{t.pk}/toggle/")
        toggle()
        toggle()  # undo
        self.assertFalse(DSREntry.objects.filter(user=self.me).exists())
        toggle()
        toggle()  # undo
        toggle()  # done
        rows = DSREntry.objects.filter(user=self.me, source="todo")
        self.assertEqual(rows.count(), 1)  # toggling never duplicates
        self.assertEqual((rows[0].task_name, rows[0].date), ("write report", timezone.localdate()))

    def test_every_action_says_what_happened_and_returns_the_list(self):
        r = self.post("/ui-api/v1/todos/", {"text": "ship it"}).json()
        self.assertEqual((r["message"], r["total"]), ('Added "ship it".', 1))
        self.assertEqual(self.post("/ui-api/v1/todos/", {"text": "  "}).status_code, 400)
        t = Todo.objects.get(text="ship it")
        self.assertIn("Marked", self.post(f"/ui-api/v1/todos/{t.pk}/toggle/").json()["message"])
        self.assertIn("Reopened", self.post(f"/ui-api/v1/todos/{t.pk}/toggle/").json()["message"])
        self.post(f"/ui-api/v1/todos/{t.pk}/toggle/")
        self.assertIn("Cleared 1 completed to-do", self.post("/ui-api/v1/todos/clear-done/").json()["message"])
        self.post("/ui-api/v1/todos/", {"text": "second"})
        t2 = Todo.objects.get(text="second")
        self.assertIn("Deleted", self.client.delete(f"/ui-api/v1/todos/{t2.pk}/").json()["message"])

    def test_the_list_orders_open_before_done_and_flags_late_ones(self):
        from datetime import timedelta

        from django.utils import timezone

        today = timezone.localdate()
        Todo.objects.create(user=self.me, text="done", done=True)
        Todo.objects.create(user=self.me, text="late", due=today - timedelta(days=1))
        Todo.objects.create(user=self.me, text="today", due=today)
        items = self.client.get("/ui-api/v1/todos/").json()["todos"]
        self.assertEqual([i["text"] for i in items][-1], "done")
        by = {i["text"]: i for i in items}
        self.assertTrue(by["late"]["late"])
        self.assertTrue(by["today"]["today"])

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

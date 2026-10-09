"""To-do side effects: the DSR row for a finished task and the daily overdue reminder."""
from django.utils import timezone

from apps.dashboards.models import Todo

OVERDUE_TITLE = "You have overdue to-dos"


def sorted_todos(user):
    """Open before done; overdue first, then high priority, then soonest due."""
    today = timezone.localdate()
    far = today.replace(year=today.year + 100)

    def key(t):
        overdue = bool(t.due and t.due < today and not t.done)
        return (t.done, not overdue, -t.priority, t.due or far, -t.pk)

    return sorted(Todo.objects.filter(user=user), key=key)


def sync_dsr(todo, company):
    """A finished to-do becomes today's DSR row (no hours: the person adds the time); undoing it removes the row."""
    from apps.dsr.models import DSREntry

    today = timezone.localdate()
    rows = DSREntry.objects.filter(company=company, user=todo.user, source="todo", source_id=todo.dsr_source_id)
    if todo.done:
        if not rows.exists():
            DSREntry.objects.create(
                company=company, user=todo.user, date=today, task_name=todo.text[:255],
                category=DSREntry.Category.OTHER, status=DSREntry.Status.COMPLETED,
                notes="From your to-do list. Add the time you spent.",
                is_auto_logged=False, source="todo", source_id=todo.dsr_source_id,
            )
    else:
        rows.filter(date=today).delete()  # a past day is closed, so leave it alone


def notify_overdue(user, company):
    """One bell + push a day while the person has overdue to-dos. Safe to call often."""
    from apps.notifications import service
    from apps.notifications.models import Notification

    today = timezone.localdate()
    late = list(Todo.objects.filter(user=user, done=False, due__lt=today).order_by("due")[:3])
    if not late:
        return None
    if Notification.objects.filter(company=company, user=user, title=OVERDUE_TITLE, created_at__date=today).exists():
        return None
    count = Todo.objects.filter(user=user, done=False, due__lt=today).count()
    names = "; ".join(t.text[:40] for t in late)
    return service.notify(
        user=user, company=company, kind=Notification.Kind.SYSTEM, title=OVERDUE_TITLE,
        body=f"{count} past their due date: {names}", url="/dashboards/#todo-card",
    )

"""Per-person read state for tickets and error groups (the sidebar badges)."""
from django.db.models import Exists, OuterRef

from apps.notifications.models import ReadMark


def unread(qs, user, kind):
    """Narrow a Ticket or ErrorGroup queryset to what `user` has not read."""
    marks = ReadMark.objects.filter(user=user, kind=kind, object_id=OuterRef("pk"))
    if kind == "error":
        marks = marks.filter(seen_count__gte=OuterRef("occurrence_count"))
    return qs.exclude(Exists(marks))


def mark(user, kind, objs):
    """Record that `user` has read these objects (a model instance or an iterable)."""
    if not hasattr(objs, "__iter__"):
        objs = [objs]
    for o in objs:
        ReadMark.objects.update_or_create(
            user=user, kind=kind, object_id=o.pk,
            defaults={"seen_count": getattr(o, "occurrence_count", 0)},
        )


def flag(page_objs, user, kind):
    """Set `.is_unread` on each object of a page, in one query."""
    objs = list(page_objs)
    ids = [o.pk for o in objs]
    seen = dict(ReadMark.objects.filter(user=user, kind=kind, object_id__in=ids).values_list("object_id", "seen_count"))
    for o in objs:
        o.is_unread = o.pk not in seen or (kind == "error" and o.occurrence_count > seen[o.pk])
    return objs

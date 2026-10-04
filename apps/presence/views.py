import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.presence import service
from apps.presence.models import PresenceSession


@require_POST
def beat(request):
    """HTTP stand-in for the presence socket.

    A tab falls back to this when its WebSocket cannot connect, which happens
    behind a proxy that does not forward the Upgrade header. It does what the
    socket does: records that this tab is here and returns who else is. It is a
    POST because it writes, so Django's CSRF check applies as usual.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "sign in"}, status=401)
    company = getattr(request, "company", None)
    if company is None:
        return JsonResponse({"error": "no workspace"}, status=403)

    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    tab = "".join(ch for ch in str(body.get("tab", "")) if ch.isalnum())[:24] or "tab"
    path = str(body.get("path", ""))[:255]
    active = bool(body.get("active", True))
    activity = service.activity_for(path)

    row, created = PresenceSession.objects.get_or_create(
        channel_name=f"http.{request.user.pk}.{tab}",
        defaults={
            "company": company,
            "user": request.user,
            "path": path,
            "activity": activity,
            "is_active": active,
        },
    )
    changed = created
    if not created:
        changed = (
            (row.path, row.activity, row.is_active) != (path, activity, active)
            or timezone.now() - row.last_seen > service.STALE_AFTER
        )
        row.path, row.activity, row.is_active = path, activity, active
        row.last_seen = timezone.now()
        row.save(update_fields=["path", "activity", "is_active", "last_seen"])

    users = service.snapshot(company)
    if changed:
        # Tabs that do have a socket should hear about this one right away.
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(
                f"presence_{company.pk}", {"type": "presence.changed", "users": users}
            )
    return JsonResponse({"users": users})

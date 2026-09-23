from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.serop.models import SeropNotification


def notify_user(user, type_, title, body="", payload=None):
    """Creates a SeropNotification row and pushes it live to the user's
    /ws/inbox/ connection if one is open. Best-effort, synchronous side
    effect — same pattern as apps.products.webhook's Discord notifiers."""
    notification = SeropNotification.objects.create(
        user=user,
        type=type_,
        title=title,
        body=body,
        payload=payload,
    )

    channel_layer = get_channel_layer()
    if channel_layer is not None:
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {"type": "notify", "notification": notification.as_json()},
            )
        except Exception:
            pass

    return notification


def notify_read(user, notification_id):
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {"type": "notify_read", "id": str(notification_id)},
            )
        except Exception:
            pass

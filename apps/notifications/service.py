"""Create notifications, and deliver them live and by web push.

Everything that wants to tell someone something calls `notify`. It skips the
person who caused the event (nobody needs a bell for their own click), stores the
row, pushes it down the open WebSocket, and sends a web push in the background if
that person has subscribed and the server has VAPID keys.
"""

import json
import logging
import threading

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from apps.notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


def safe_path(url):
    """A site-relative path or nothing. Stops a notification from being an open
    redirect, whatever text a caller passes in."""
    url = (url or "").strip()
    if url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url[:255]
    return ""


def group_name(user_id):
    return f"notify_{user_id}"


def unread_count(user, company):
    return Notification.objects.filter(user=user, company=company, read_at__isnull=True).count()


def notify(*, user, company, kind, title, body="", url="", actor=None):
    """Tell one person something. Returns the row, or None if skipped."""
    if user is None or company is None:
        return None
    if actor is not None and actor.pk == user.pk:
        return None
    notification = Notification.objects.create(
        company=company,
        user=user,
        kind=kind,
        title=title[:200],
        body=(body or "")[:300],
        url=safe_path(url),
        actor=actor,
    )
    _push_live(notification, unread_count(user, company))
    _push_web(notification)
    return notification


def notify_many(users, **kwargs):
    """`notify` for each distinct user. Returns the notifications created."""
    seen, created = set(), []
    for user in users:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        row = notify(user=user, **kwargs)
        if row is not None:
            created.append(row)
    return created


def mark_read(user, company, ids=None):
    rows = Notification.objects.filter(user=user, company=company, read_at__isnull=True)
    if ids is not None:
        rows = rows.filter(pk__in=ids)
    return rows.update(read_at=timezone.now())


def _push_live(notification, unread):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            group_name(notification.user_id),
            {
                "type": "notification.new",
                "notification": notification.as_json(),
                "unread": unread,
                "company_id": notification.company_id,
            },
        )
    except Exception:  # best effort: the row is saved, the bell catches up on load
        logger.exception("could not push notification live")


def _push_web(notification):
    if not getattr(settings, "WEBPUSH_VAPID_PRIVATE_KEY", ""):
        return
    subs = list(PushSubscription.objects.filter(user_id=notification.user_id))
    if not subs:
        return
    payload = json.dumps(
        {
            "title": notification.title,
            "body": notification.body,
            "url": f"/notifications/{notification.pk}/open/",
            "tag": f"n{notification.pk}",
        }
    )
    threading.Thread(target=_send_all, args=(subs, payload), daemon=True).start()


def _send_all(subs, payload):
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush is not installed; skipping web push")
        return
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEBPUSH_VAPID_SUBJECT},
                timeout=5,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):  # the browser dropped the subscription
                PushSubscription.objects.filter(pk=sub.pk).delete()
            else:
                logger.warning("web push failed: %s", exc)
        except Exception:
            logger.exception("web push failed")

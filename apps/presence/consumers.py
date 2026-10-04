import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Membership
from apps.presence import service
from apps.presence.models import PresenceSession

logger = logging.getLogger(__name__)


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    """Live "who is online" feed for the signed-in company.

    Authenticated by the session cookie (AuthMiddlewareStack) and guarded by an
    Origin check in routing, so another site cannot open this socket with a
    visitor's cookies. The company is the one the user has switched to, taken
    from the session the same way the request middleware does.

    Browser to server:  {"type": "activity", "path": "/tickets/4/", "active": true}
                        {"type": "ping"}
    Server to browser:  {"event": "presence", "users": [...]}
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        company_id = await self._company_id(user)
        if company_id is None:
            await self.close(code=4403)
            return

        self.user = user
        self.company_id = company_id
        self.group_name = f"presence_{company_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._create_session()
        await self._broadcast()

    async def disconnect(self, close_code):
        if not hasattr(self, "group_name"):
            return
        await self._delete_session()
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self._broadcast()

    async def receive_json(self, content, **kwargs):
        kind = content.get("type") if isinstance(content, dict) else None
        if kind == "ping":
            changed = await self._touch()
        elif kind == "activity":
            path = str(content.get("path", ""))[:255]
            active = bool(content.get("active", True))
            changed = await self._set_activity(path, active)
        else:
            return
        if changed:
            await self._broadcast()

    async def presence_changed(self, event):
        await self.send_json({"event": "presence", "users": event["users"]})

    async def _broadcast(self):
        users = await database_sync_to_async(service.snapshot_for_company_id)(self.company_id)
        await self.channel_layer.group_send(
            self.group_name, {"type": "presence.changed", "users": users}
        )

    @database_sync_to_async
    def _company_id(self, user):
        memberships = list(Membership.objects.filter(user=user).values_list("company_id", flat=True))
        if not memberships:
            return None
        session = self.scope.get("session")
        active = session.get(settings.ACTIVE_COMPANY_SESSION_KEY) if session else None
        return active if active in memberships else memberships[0]

    @database_sync_to_async
    def _create_session(self):
        PresenceSession.objects.update_or_create(
            channel_name=self.channel_name,
            defaults={
                "company_id": self.company_id,
                "user": self.user,
                "path": "",
                "activity": "Just signed in",
                "is_active": True,
                "last_seen": timezone.now(),
            },
        )

    @database_sync_to_async
    def _delete_session(self):
        PresenceSession.objects.filter(channel_name=self.channel_name).delete()

    @database_sync_to_async
    def _touch(self):
        """Heartbeat. Returns True if the tab had gone stale, so others re-sync."""
        row = PresenceSession.objects.filter(channel_name=self.channel_name).first()
        if row is None:
            return False
        was_stale = timezone.now() - row.last_seen > service.STALE_AFTER
        row.last_seen = timezone.now()
        row.save(update_fields=["last_seen"])
        return was_stale

    @database_sync_to_async
    def _set_activity(self, path, active):
        row = PresenceSession.objects.filter(channel_name=self.channel_name).first()
        if row is None:
            return False
        activity = service.activity_for(path)
        changed = (row.path, row.activity, row.is_active) != (path, activity, active)
        row.path, row.activity, row.is_active = path, activity, active
        row.last_seen = timezone.now()
        row.save(update_fields=["path", "activity", "is_active", "last_seen"])
        return changed

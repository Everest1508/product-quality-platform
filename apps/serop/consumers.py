from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.models import ExternalAccessToken


class InboxConsumer(AsyncJsonWebsocketConsumer):
    """Live notification stream for the Serop desktop app, matching the
    {token} query-string auth and {event, ...} message shape the renderer's
    connectInboxWebSocket (src/api/client.ts) already expects."""

    async def connect(self):
        query = parse_qs(self.scope["query_string"].decode())
        token = (query.get("token") or [""])[0]
        token_obj = await database_sync_to_async(ExternalAccessToken.validate)(token) if token else None
        if not token_obj:
            await self.close(code=4001)
            return

        self.user = token_obj.user
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notify(self, event):
        await self.send_json({"event": "notification", "notification": event["notification"]})

    async def notify_read(self, event):
        await self.send_json({"event": "notification_read", "id": event["id"]})

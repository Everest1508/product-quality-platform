"""
ASGI config for core project.

HTTP goes to Django. WebSockets are split by who connects:

* /ws/presence/ is the web UI. It authenticates with the session cookie, so it
  sits behind an Origin check (otherwise any website could open it with a
  visitor's cookies) and AuthMiddlewareStack.
* /ws/inbox/ is the Serop desktop app. It authenticates with a bearer token in
  the query string, has no cookies, and is not a browser origin, so neither
  wrapper applies.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.urls import path  # noqa: E402

from apps.presence.consumers import PresenceConsumer  # noqa: E402
from apps.serop.routing import websocket_urlpatterns as serop_urls  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path(
            "ws/presence/",
            AllowedHostsOriginValidator(AuthMiddlewareStack(PresenceConsumer.as_asgi())),
        ),
        *serop_urls,
    ]),
})

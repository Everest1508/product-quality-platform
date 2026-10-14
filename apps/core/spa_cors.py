"""Let a front end hosted on its own address (for example Vercel) call this site's JSON endpoints with the login cookie.

Off unless `FRONTEND_ORIGINS` is set. Only those exact origins are allowed, only for the paths the web app uses, and
credentials are allowed only for them. Everything else (the SDK API, the Serop endpoints) is untouched: those keep
their own rules in settings (`CORS_URLS_REGEX`).
"""

from django.conf import settings
from django.http import HttpResponse

# What the web app calls: its JSON API, the bell, search, the changelog, the presence heartbeat and the notification link.
PATHS = ("/ui-api/", "/notifications/", "/search/", "/api/v1/changelog/", "/presence/beat/")
HEADERS = "Content-Type, X-CSRFToken, Accept"


class SpaCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _allowed(self, request):
        origin = request.headers.get("Origin", "")
        if origin and origin in getattr(settings, "FRONTEND_ORIGINS", []) and request.path.startswith(PATHS):
            return origin
        return ""

    def __call__(self, request):
        origin = self._allowed(request)
        if origin and request.method == "OPTIONS" and "Access-Control-Request-Method" in request.headers:
            response = HttpResponse(status=204)
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = HEADERS
            response["Access-Control-Max-Age"] = "600"
        else:
            response = self.get_response(request)
        if origin:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Vary"] = (response.get("Vary", "") + ", Origin").lstrip(", ")
        return response

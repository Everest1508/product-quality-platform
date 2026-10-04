"""PWA endpoints: web app manifest, service worker, offline page.

The service worker has to be served from the site root so its scope covers
every page, which is why these live as views instead of static files (the
project has no static pipeline anyway, see apps/core/brand.py).
"""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

THEME_COLOR = "#ffffff"
BACKGROUND_COLOR = "#ffffff"


def manifest(request):
    def icon(name, size, purpose):
        return {"src": f"/brand/{name}", "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}

    data = {
        "id": "/",
        "name": "PQ Platform",
        "short_name": "PQ",
        "description": "Errors, tickets, feedback, attendance and payroll, kept per product.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": BACKGROUND_COLOR,
        "theme_color": THEME_COLOR,
        "icons": [
            icon("pwa-192.png", 192, "any"),
            icon("pwa-512.png", 512, "any"),
            icon("pwa-maskable-192.png", 192, "maskable"),
            icon("pwa-maskable-512.png", 512, "maskable"),
        ],
        "shortcuts": [
            {"name": "Tickets", "url": "/tickets/", "icons": [icon("pwa-192.png", 192, "any")]},
            {"name": "Errors", "url": "/errors/", "icons": [icon("pwa-192.png", 192, "any")]},
            {"name": "Attendance", "url": "/attendance/", "icons": [icon("pwa-192.png", 192, "any")]},
        ],
    }
    response = JsonResponse(data, json_dumps_params={"indent": 2})
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "public, max-age=3600"
    return response


@never_cache
def service_worker(request):
    # Rendered as a template so the cache name changes with APP_VERSION, which
    # makes the browser install the new worker and drop the old cache.
    response = render(
        request,
        "pwa/sw.js",
        {"version": getattr(settings, "APP_VERSION", "0.0.0")},
        content_type="application/javascript",
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "pwa/offline.html", {"theme_color": THEME_COLOR})

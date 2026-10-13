"""Error responses without Django's HTML pages: JSON for API paths, the React shell (which shows its own message) for pages."""
from django.http import JsonResponse

from apps.uiapi.shell import render_shell

API_PREFIXES = ("/api/", "/ui-api/", "/oauth/")
DETAIL = {400: "Bad request.", 403: "Forbidden.", 404: "Not found.", 500: "Server error."}


def _respond(request, status):
    if request.path.startswith(API_PREFIXES):
        return JsonResponse({"detail": DETAIL[status]}, status=status)
    try:
        response = render_shell(request)
    except Exception:  # the shell itself must never turn a 500 into a second one
        return JsonResponse({"detail": DETAIL[status]}, status=status)
    response.status_code = status
    return response


def bad_request(request, exception=None):
    return _respond(request, 400)


def forbidden(request, exception=None):
    return _respond(request, 403)


def not_found(request, exception=None):
    return _respond(request, 404)


def server_error(request):
    return _respond(request, 500)

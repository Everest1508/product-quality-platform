import json
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.db import connection
from django.shortcuts import redirect

from apps.accounts.access import NO_WORKSPACE_MESSAGE, has_no_workspace
from apps.accounts.models import Membership
from apps.core.templatetags.toast_tags import TOAST_TAGS


class ServerTimingMiddleware:
    """Tell the browser how long the server took, so a slow page can be blamed correctly.

    Adds `Server-Timing: app;dur=<ms>, db;dur=<ms>;desc="<n> queries"`. In the browser's
    Network tab the Timing panel shows it. If "Waiting for server response" is much bigger
    than `app`, the time is going on the network or a proxy, not in this app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        stats = {"n": 0, "db": 0.0}

        def count(execute, sql, params, many, context):
            start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                stats["n"] += 1
                stats["db"] += time.perf_counter() - start

        start = time.perf_counter()
        with connection.execute_wrapper(count):
            response = self.get_response(request)
        response["Server-Timing"] = (
            f'app;dur={(time.perf_counter() - start) * 1000:.0f}, '
            f'db;dur={stats["db"] * 1000:.0f};desc="{stats["n"]} queries"'
        )
        return response


class CurrentCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.company_role = None

        if request.user.is_authenticated:
            memberships = list(
                Membership.objects.select_related("company")
                .filter(user=request.user)
            )
            if memberships:
                active_id = request.session.get(settings.ACTIVE_COMPANY_SESSION_KEY)
                membership = next(
                    (m for m in memberships if m.company_id == active_id),
                    memberships[0],
                )
                request.company = membership.company
                request.company_role = membership.role
            elif has_no_workspace(request.user):
                # Removed from their team while signed in: end the session
                # rather than leave them in the app or offer company setup.
                logout(request)
                messages.error(request, NO_WORKSPACE_MESSAGE)
                return redirect("accounts:login")

        response = self.get_response(request)
        return response


class HtmxMessagesMiddleware:
    """Hand queued Django messages to htmx as an `HX-Trigger` toast event.

    An htmx swap renders a fragment, not the shell, so the toast seed in
    base.html never runs and the message would surface on some later page.
    Redirects and full pages that already consumed the queue are skipped.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get("HX-Request") != "true" or response.status_code in (301, 302, 303, 307, 308):
            return response
        storage = getattr(request, "_messages", None)
        if storage is None or storage.used or "HX-Trigger" in response.headers:
            return response
        items = [{"text": str(m), "tags": m.tags if m.tags in TOAST_TAGS else "info"} for m in storage]
        if items:
            response.headers["HX-Trigger"] = json.dumps({"django-message": {"messages": items}})
        return response

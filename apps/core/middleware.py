import json

from django.conf import settings

from apps.accounts.models import Membership
from apps.core.templatetags.toast_tags import TOAST_TAGS


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

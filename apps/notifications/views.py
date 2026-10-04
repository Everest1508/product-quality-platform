import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.notifications import service
from apps.notifications.models import Notification, PushSubscription


def _mine(request):
    return Notification.objects.filter(user=request.user, company=request.company).select_related("actor")


class FeedView(CompanyMemberRequiredMixin, View):
    """Recent notifications and the unread count, for the bell on page load."""

    def get(self, request):
        items = [n.as_json() for n in _mine(request)[:15]]
        return JsonResponse({"unread": service.unread_count(request.user, request.company), "items": items})


class ListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        rows = _mine(request)
        only_unread = request.GET.get("filter") == "unread"
        if only_unread:
            rows = rows.filter(read_at__isnull=True)
        return render(request, "notifications/list.html", {
            "notifications": rows[:100],
            "only_unread": only_unread,
            "unread": service.unread_count(request.user, request.company),
        })


class OpenView(CompanyMemberRequiredMixin, View):
    """Mark one read and go where it points. A plain link, so it works without
    JavaScript and from a web push tap."""

    def get(self, request, pk):
        notification = get_object_or_404(_mine(request), pk=pk)
        service.mark_read(request.user, request.company, ids=[notification.pk])
        return redirect(service.safe_path(notification.url) or "notifications:list")


class MarkAllReadView(CompanyMemberRequiredMixin, View):
    def post(self, request):
        service.mark_read(request.user, request.company)
        if request.headers.get("HX-Request") == "true" or request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse({"unread": 0})
        return redirect("notifications:list")


class PushSubscribeView(CompanyMemberRequiredMixin, View):
    """Store this browser's push subscription for the signed-in user."""

    def post(self, request):
        try:
            data = json.loads(request.body or b"{}")
            endpoint = data["endpoint"]
            keys = data["keys"]
            p256dh, auth = keys["p256dh"], keys["auth"]
        except (ValueError, KeyError, TypeError):
            return HttpResponseBadRequest("Invalid subscription.")
        if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            return HttpResponseBadRequest("Invalid endpoint.")
        # update_or_create on the endpoint: a browser that signs in as someone
        # else takes the subscription with it instead of notifying the old user.
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": str(p256dh)[:255],
                "auth": str(auth)[:255],
                "user_agent": request.headers.get("User-Agent", "")[:255],
            },
        )
        return JsonResponse({"ok": True})


class PushUnsubscribeView(CompanyMemberRequiredMixin, View):
    def post(self, request):
        try:
            endpoint = json.loads(request.body or b"{}").get("endpoint", "")
        except ValueError:
            return HttpResponseBadRequest("Invalid body.")
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return JsonResponse({"ok": True})

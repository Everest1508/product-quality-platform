import json
from urllib.parse import urlparse

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlencode

from apps.accounts.models import ExternalAccessToken, ExternalAuthCode
from apps.core.mixins import CompanyMemberRequiredMixin, LoginRequiredMixin
from apps.uiapi.shell import render_shell


def _user_json(user):
    display_name = (f"{user.first_name} {user.last_name}".strip()) or user.username
    return {
        "id": str(user.pk),
        "email": user.email or None,
        "displayName": display_name,
        "isGuest": False,
    }


def _is_loopback_redirect(redirect_uri):
    try:
        parsed = urlparse(redirect_uri)
    except ValueError:
        return False
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")


class LoginView(View):
    """The sign-in page is React (public, no shell). Signed-in visitors are sent on."""

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return render_shell(request)


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "Signed out.")
        return redirect("accounts:login")


class DashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return redirect("dashboards:index")


class CompanySetupView(LoginRequiredMixin, View):
    """First-run setup for someone with no workspace yet: a public-style React page (no sidebar to build)."""

    def get(self, request):
        if request.company:
            return redirect("accounts:dashboard")
        return render_shell(request)


class TeamListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return render_shell(request)


class TeamMemberView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        return render_shell(request)


class ProfileView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return render_shell(request)


class OAuthAuthorizeView(View):
    """External sign-in entry point for third-party clients (currently just the Serop desktop app).
    Loopback-only redirect_uri to keep this from being usable as an open redirect. A signed-in person
    is sent straight back with a code; anyone else gets the React sign-in page, which posts to the API."""

    def get(self, request):
        redirect_uri = request.GET.get("redirect_uri", "")
        if not _is_loopback_redirect(redirect_uri):
            return HttpResponseBadRequest("redirect_uri must be a loopback (127.0.0.1/localhost) address.")
        if request.user.is_authenticated:
            _code_obj, raw_code = ExternalAuthCode.issue(request.user, request.GET.get("client_id", ""), redirect_uri)
            return redirect(f"{redirect_uri}?{urlencode({'code': raw_code, 'state': request.GET.get('state', '')})}")
        return render_shell(request)


@method_decorator(csrf_exempt, name="dispatch")
class OAuthTokenView(View):
    """Exchanges a one-time authorize code for a bearer token. Called
    server-to-server by the Serop Electron main process, not from a browser
    session, so it carries no CSRF cookie and is exempted."""

    def post(self, request):
        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON body.")

        code = body.get("code", "")
        user = ExternalAuthCode.exchange(code) if code else None
        if not user:
            return JsonResponse({"ok": False, "error": "Invalid or expired code."}, status=400)

        _token_obj, raw_token = ExternalAccessToken.create_token(user, client_id=body.get("client_id", "serop"))
        return JsonResponse({"ok": True, "token": raw_token, "user": _user_json(user)})


class OAuthMeView(View):
    def get(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse({"ok": False, "error": "Missing bearer token."}, status=401)

        token_obj = ExternalAccessToken.validate(auth_header[len("Bearer "):])
        if not token_obj:
            return JsonResponse({"ok": False, "error": "Invalid or revoked token."}, status=401)

        return JsonResponse({"ok": True, "user": _user_json(token_obj.user)})

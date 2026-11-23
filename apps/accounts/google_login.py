"""TEMPORARY: sign in / sign up to the CRM with Google.

To remove: delete this file, the `google/` line in urls.py, the one line in
LoginView._render, the button block in login.html, and the two settings.
Off unless CRM_GOOGLE_LOGIN=1. Existing accounts are linked by verified email;
a new email becomes a `viewer` in the first company (sees nothing until an
owner raises the role). CRM_GOOGLE_LOGIN_DOMAIN, if set, limits who may sign in.
"""
import json

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from django.views import View

from apps.accounts.access import NO_WORKSPACE_MESSAGE, has_no_workspace
from apps.accounts.models import Company, Membership
from apps.appauth.google import verify_google_id_token
from apps.appauth.service import AuthError
from apps.core.redirects import safe_next

User = get_user_model()


def client_id():
    """Web client id for the login button, or "" when the feature is off."""
    if not settings.CRM_GOOGLE_LOGIN:
        return ""
    return (settings.GOOGLE_CLIENT_IDS or [""])[0]


class GoogleLoginView(View):
    def post(self, request):
        if not client_id():
            return JsonResponse({"error": "Google sign-in is off."}, status=404)
        try:
            data = json.loads(request.body or b"{}")
            claims = verify_google_id_token(data.get("credential"))
        except (ValueError, AttributeError, AuthError):
            return JsonResponse({"error": "Google sign-in failed. Try again."}, status=401)
        email = claims["email"].strip().lower()
        domain = settings.CRM_GOOGLE_LOGIN_DOMAIN
        if domain and not email.endswith("@" + domain.lower().lstrip("@")):
            return JsonResponse({"error": "That Google account is not allowed here."}, status=403)

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            username, n = email[:150], 1
            while User.objects.filter(username=username).exists():
                n += 1
                username = f"{email[:140]}-{n}"
            user = User(username=username, email=email, first_name=(claims.get("given_name") or "")[:150],
                        last_name=(claims.get("family_name") or "")[:150])
            user.set_unusable_password()
            user.save()
            company = Company.objects.first()
            if company:
                Membership.objects.create(user=user, company=company, role=Membership.Role.VIEWER)
        if not user.is_active or has_no_workspace(user):
            return JsonResponse({"error": NO_WORKSPACE_MESSAGE}, status=403)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse({"next": safe_next(data.get("next")) or "/"})

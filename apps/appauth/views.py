from django.db import IntegrityError
from django.http import HttpResponse
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.appauth import apple, google, service
from apps.appauth.models import AppUser
from apps.appauth.service import AuthError, normalize_email


class AppBearerAuthentication(BaseAuthentication):
    """`Authorization: Bearer <jwt>`. Re-reads the user every request, so revoking bites immediately."""

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise AuthError("invalid_token", "Missing bearer token.", 401)
        user = service.user_from_access_token(header[7:].strip())
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"


class Base(APIView):
    authentication_classes = []
    permission_classes = []

    def handle_exception(self, exc):
        if isinstance(exc, AuthError):
            return Response({"code": exc.code, "message": exc.message}, status=exc.status)
        return super().handle_exception(exc)


def _profile(u):
    return {"id": str(u.id), "email": u.email, "name": u.name, "avatar_url": u.avatar_url,
            "auth_provider": u.auth_provider, "status": u.status}


def _session(request, user, event, extra=None):
    service.ensure_active(user)
    service.touch_login(user)
    service.log_event(user, event, request)
    return Response({**service.issue_tokens(user, request), "user": _profile(user), **(extra or {})})


class RegisterView(Base):
    def post(self, request):
        email = normalize_email(request.data.get("email"))
        if not email or "@" not in email or len(email) > 254:
            raise AuthError("invalid_email", "Enter a valid email address.", 400)
        service.throttle_request(request, "register", email, email_limit=5)
        try:
            user = service.register(email, request.data.get("password"), request.data.get("name"))
        except IntegrityError:  # two simultaneous signups
            raise AuthError("email_exists", "An account with this email already exists.", 409)
        service.log_event(user, "register", request)
        service.send_verification(user)
        # No tokens yet: the app signs in only after the emailed code is confirmed (verify-email-otp).
        return Response({"email_verification_required": True, "email": user.email}, status=201)


class LoginView(Base):
    def post(self, request):
        email = normalize_email(request.data.get("email"))
        service.throttle_request(request, "login", email)
        user = AppUser.objects.filter(email=email).exclude(status="deleted").first()
        password = request.data.get("password")
        ok = service.verify_password(user, password if isinstance(password, str) else "")
        if not ok:
            raise AuthError("invalid_credentials", "Invalid email or password", 401)
        service.ensure_active(user)
        if not user.email_verified:
            service.send_verification(user)  # throttled above; the app opens its code screen on this error
            raise AuthError("email_not_verified", "Confirm your email to continue. We sent you a new code.", 403)
        return _session(request, user, "login")


class GoogleView(Base):
    def post(self, request):
        service.throttle_request(request, "google")
        claims = google.verify_google_id_token(request.data.get("id_token"))
        user = service.login_with_identity("google", claims)
        return _session(request, user, "google_login")


class AppleView(Base):
    def post(self, request):
        service.throttle_request(request, "apple")
        claims = apple.verify_apple_identity_token(request.data.get("identity_token"))
        # Apple puts the person's name only in the first-sign-in response to the app, never in the token.
        # It is display-only, capped, and used only when the account is created.
        name = request.data.get("name")
        user = service.login_with_identity("apple", claims, name.strip() if isinstance(name, str) else "")
        return _session(request, user, "apple_login")


def reauthenticate(user, data):
    """Sensitive actions need proof it is the owner, not just a stolen access token: the password, or a fresh
    Google/Apple token for the account's own provider id."""
    service.throttle("reauth", str(user.id), 10)
    bad = AuthError("reauth_failed", "Could not confirm it is you.", 403)
    pw = data.get("current_password")
    if isinstance(pw, str) and pw:
        if user.password_hash and service.verify_password(user, pw):
            return
        raise bad
    for field, verify, sub in (("id_token", google.verify_google_id_token, user.google_sub),
                               ("identity_token", apple.verify_apple_identity_token, user.apple_sub)):
        if data.get(field):
            if sub and verify(data[field])["sub"] == sub:
                return
            raise bad
    raise AuthError("reauth_required", "Send current_password, or id_token / identity_token for your sign-in method.", 400)


class ChangePasswordView(Base):
    authentication_classes = [AppBearerAuthentication]

    def post(self, request):
        user = request.user
        service.check_new_password(request.data.get("new_password"))
        reauthenticate(user, request.data)
        user.password_hash = service.hash_password(request.data["new_password"])
        user.save(update_fields=["password_hash"])
        service.force_logout(user)  # every session ends, including this one...
        service.log_event(user, "password_change", request)
        return Response({"ok": True, **service.issue_tokens(user, request)})  # ...so this device gets a fresh pair


class LogoutAllView(Base):
    authentication_classes = [AppBearerAuthentication]

    def post(self, request):
        service.force_logout(request.user)
        service.log_event(request.user, "force_logout", request)
        return Response({"ok": True})


class RefreshView(Base):
    def post(self, request):
        service.throttle_request(request, "refresh", ip_limit=120)
        return Response(service.rotate(request.data.get("refresh_token"), request))


class LogoutView(Base):
    def post(self, request):
        raw = request.data.get("refresh_token")
        service.revoke_refresh(raw)
        return Response({"ok": True})


class ForgotPasswordView(Base):
    def post(self, request):
        email = normalize_email(request.data.get("email"))
        service.throttle_request(request, "forgot", email, email_limit=3)
        user = AppUser.objects.filter(email=email).exclude(status="deleted").first()
        if user and user.status == "active":
            service.send_reset(user)
            service.log_event(user, "forgot_password", request)
        return Response({"ok": True, "message": "If that email has an account, a reset code is on its way."})


class VerifyResetOtpView(Base):
    """Step 2 of a reset: only a correct emailed code earns the token that reset-password needs."""

    def post(self, request):
        email = normalize_email(request.data.get("email"))
        service.throttle_request(request, "reset_code", email, email_limit=6)
        return Response({"reset_token": service.reset_token_from_otp(email, request.data.get("code"))})


class ResetPasswordView(Base):
    def post(self, request):
        service.throttle_request(request, "reset")
        user = service.reset_password(request.data.get("token") or "", request.data.get("new_password"))
        service.log_event(user, "password_reset", request)
        return Response({"ok": True})


class VerifyEmailOtpView(Base):
    def post(self, request):
        email = normalize_email(request.data.get("email"))
        service.throttle_request(request, "verify_code", email, email_limit=6)
        user = service.verify_email_otp(email, request.data.get("code"))
        return _session(request, user, "verify_email")


class ResendVerificationView(Base):
    def post(self, request):
        email = normalize_email(request.data.get("email"))
        service.throttle_request(request, "resend", email, email_limit=3)
        user = service._user_by_email(email)
        if user and user.status == "active" and not user.email_verified:
            service.send_verification(user)
        return Response({"ok": True, "message": "If that email needs confirming, a new code is on its way."})


class VerifyEmailView(Base):
    def get(self, request):
        try:
            service.verify_email_token(request.query_params.get("token", ""))
        except AuthError:
            return HttpResponse("This verification link is invalid or has expired.", status=400)
        return HttpResponse("Email verified. You can return to CardSnap.")


class MeView(Base):
    authentication_classes = [AppBearerAuthentication]

    def get(self, request):
        return Response(_profile(request.user))

    def delete(self, request):
        # An account with no password (Google or Apple only) has nothing to retype: a plain confirmation is enough.
        if request.user.password_hash or request.data.get("confirm") != "DELETE":
            reauthenticate(request.user, request.data)
        service.log_event(request.user, "delete_account", request)  # unlinked when the row goes
        service.delete_account(request.user)
        return Response({"ok": True})

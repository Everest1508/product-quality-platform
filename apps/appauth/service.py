"""All CardSnap auth rules. Views stay thin; nothing here logs secrets."""
import hashlib
import hmac
import secrets
import time
import uuid
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from apps.appauth.models import AppAuthEvent, AppRefreshToken, AppUser

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
RESET_TTL = 30 * 60
VERIFY_TTL = 3 * 24 * 3600
OTP_WINDOW = 600  # a code is good for at least 10 minutes (this window and the one before it)
MIN_PASSWORD = 8


class AuthError(Exception):
    def __init__(self, code, message, status):
        self.code, self.message, self.status = code, message, status


def normalize_email(email):
    return (email or "").strip().lower()


# --- passwords -------------------------------------------------------------
def hash_password(raw):
    return make_password(raw, hasher="argon2")


def verify_password(user, raw):
    # Hash a dummy when there is no password so unknown/Google-only accounts cost the same time.
    return check_password(raw, user.password_hash if user and user.password_hash else _DUMMY) and bool(user and user.password_hash)


_DUMMY = make_password("x", hasher="argon2")


def check_new_password(raw):
    if not isinstance(raw, str) or len(raw) < MIN_PASSWORD:
        raise AuthError("weak_password", f"Password must be at least {MIN_PASSWORD} characters.", 400)


# --- throttling ------------------------------------------------------------
# ponytail: Django cache counters; default LocMem is per worker. Set a shared CACHES (Redis) for exact limits.
def throttle(scope, key, limit, window=600):
    k = f"appauth:{scope}:{hashlib.sha256(key.encode()).hexdigest()[:24]}"
    cache.add(k, 0, window)
    try:
        n = cache.incr(k)
    except ValueError:
        cache.set(k, 1, window)
        n = 1
    if n > limit:
        raise AuthError("rate_limited", "Too many attempts. Try again later.", 429)


def client_ip(request):
    # Behind the TLS proxy REMOTE_ADDR is the proxy; the last X-Forwarded-For hop is the one it appended.
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            return xff.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")


def throttle_request(request, scope, email="", ip_limit=30, email_limit=10):
    throttle(scope + ":ip", client_ip(request) or "?", ip_limit)
    if email:
        throttle(scope + ":email", email, email_limit)


# --- audit -----------------------------------------------------------------
def log_event(user, event, request=None):
    AppAuthEvent.objects.create(
        user=user, event=event,
        ip=client_ip(request) if request else None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )


# --- access tokens ---------------------------------------------------------
def jwt_secret():
    return settings.APPAUTH_JWT_SECRET


def make_access_token(user):
    now = timezone.now()
    return jwt.encode(
        {"sub": str(user.id), "token_version": user.token_version, "iat": now, "exp": now + ACCESS_TTL},
        jwt_secret(), algorithm="HS256",
    )


def user_from_access_token(raw):
    """The active user for a bearer token. 401 for bad tokens, 403 account_revoked for revoked users."""
    try:
        claims = jwt.decode(raw, jwt_secret(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
        user = AppUser.objects.get(pk=claims["sub"])
    except (jwt.PyJWTError, AppUser.DoesNotExist, ValueError, KeyError):
        raise AuthError("invalid_token", "Invalid or expired token.", 401)
    ensure_active(user)  # revoked -> 403, deleted -> 401; checked on every request, not only at refresh
    if claims.get("token_version") != user.token_version:
        raise AuthError("invalid_token", "Invalid or expired token.", 401)
    return user


def ensure_active(user):
    if user.status == "revoked":
        raise AuthError("account_revoked", "This account has been revoked.", 403)
    if user.status != "active":
        raise AuthError("invalid_token", "Invalid or expired token.", 401)


# --- refresh tokens --------------------------------------------------------
def _hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_tokens(user, request=None, family=None):
    raw = secrets.token_urlsafe(48)
    AppRefreshToken.objects.create(
        user=user, token_hash=_hash(raw), family=family or uuid.uuid4(),
        expires_at=timezone.now() + REFRESH_TTL,
        device_info=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )
    return {"access_token": make_access_token(user), "refresh_token": raw, "token_type": "Bearer",
            "expires_in": int(ACCESS_TTL.total_seconds())}


def rotate(raw, request=None):
    row = AppRefreshToken.objects.select_related("user").filter(token_hash=_hash(raw or "")).first()
    bad = AuthError("invalid_refresh_token", "Invalid or expired refresh token.", 401)
    if not row:
        raise bad
    if row.revoked_at:
        # A rotated/revoked token came back: someone copied it. Kill the whole family.
        AppRefreshToken.objects.filter(family=row.family, revoked_at__isnull=True).update(revoked_at=timezone.now())
        log_event(row.user, "refresh_reuse", request)
        raise bad
    if row.expires_at <= timezone.now():
        raise bad
    ensure_active(row.user)
    row.revoked_at = timezone.now()
    row.save(update_fields=["revoked_at"])
    log_event(row.user, "refresh", request)
    return issue_tokens(row.user, request, family=row.family)


def revoke_refresh(raw):
    AppRefreshToken.objects.filter(token_hash=_hash(raw or ""), revoked_at__isnull=True).update(revoked_at=timezone.now())


def force_logout(user):
    """Kill every session: refresh tokens deleted, outstanding access tokens invalidated."""
    user.refresh_tokens.all().delete()
    AppUser.objects.filter(pk=user.pk).update(token_version=user.token_version + 1)
    user.token_version += 1


# --- accounts --------------------------------------------------------------
def touch_login(user):
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])


def register(email, password, name):
    check_new_password(password)
    existing = AppUser.objects.filter(email=email).first()
    if existing and not existing.email_verified and existing.auth_provider == "password" and existing.status == "active":
        # Signed up before but never confirmed the email: nobody has proved ownership, so let the sign-up be
        # retried (new password and name). The code still goes only to the mailbox owner.
        existing.password_hash = hash_password(password)
        existing.name = (name or existing.name or "")[:255]
        existing.save(update_fields=["password_hash", "name"])
        return existing
    if existing:
        # Never set a password on an account just because someone typed its email: that would let anyone
        # pre-claim a Google user's account. Linking a password to it goes through reset-password.
        raise AuthError("email_exists", "An account with this email already exists. Sign in, or use "
                        "'Forgot password' to set a password.", 409)
    return AppUser.objects.create(email=email, name=(name or "")[:255], password_hash=hash_password(password))


def login_with_identity(provider, claims, client_name=""):
    """Find-or-create/link by the provider's stable `sub` (google | apple), else by verified email."""
    field = provider + "_sub"
    sub = claims["sub"]
    email = normalize_email(claims.get("email"))
    user = AppUser.objects.filter(**{field: sub}).first() or (AppUser.objects.filter(email=email).first() if email else None)
    if user is None:
        if not email:  # Apple only sends the email on the first sign-in
            raise AuthError("email_missing", "The provider did not share an email address.", 400)
        return AppUser.objects.create(
            email=email, auth_provider=provider, email_verified=True, **{field: sub},
            name=(claims.get("name") or client_name or "")[:255], avatar_url=(claims.get("picture") or "")[:500],
        )
    if user.status == "deleted" or getattr(user, field) not in (None, sub):
        raise AuthError("invalid_token", "Invalid token.", 401)
    if not getattr(user, field):
        # Link. If the password was set by someone who never proved the email, drop it: the provider just proved it.
        if not user.email_verified and user.password_hash:
            user.password_hash = None
            force_logout(user)
        setattr(user, field, sub)
        user.email_verified = True
        user.name = user.name or (claims.get("name") or client_name or "")[:255]
        user.avatar_url = user.avatar_url or (claims.get("picture") or "")[:500]
        user.save()
    return user


def delete_account(user):
    user.status, user.deleted_at = "deleted", timezone.now()
    user.save(update_fields=["status", "deleted_at"])
    force_logout(user)


# --- signed one-shot tokens (no table needed) --------------------------------
def _fingerprint(user):
    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:20]


def make_verify_token(user):
    return signing.dumps({"u": str(user.id), "e": user.email}, salt="appauth.verify")


def verify_email_token(token):
    try:
        data = signing.loads(token, salt="appauth.verify", max_age=VERIFY_TTL)
        user = AppUser.objects.get(pk=data["u"], email=data["e"])
    except (signing.BadSignature, AppUser.DoesNotExist, KeyError, ValueError):
        raise AuthError("invalid_token", "This link is invalid or has expired.", 400)
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return user


def make_reset_token(user):
    # Embeds a fingerprint of the current password, so it stops working the moment the password changes: single use.
    return signing.dumps({"u": str(user.id), "p": _fingerprint(user)}, salt="appauth.reset")


def reset_password(token, new_password):
    check_new_password(new_password)
    bad = AuthError("invalid_token", "This reset link is invalid or has expired.", 400)
    try:
        data = signing.loads(token, salt="appauth.reset", max_age=RESET_TTL)
        user = AppUser.objects.get(pk=data["u"])
    except (signing.BadSignature, AppUser.DoesNotExist, ValueError, KeyError):
        raise bad
    if not hmac.compare_digest(data["p"], _fingerprint(user)) or user.status == "deleted":
        raise bad
    user.password_hash = hash_password(new_password)
    user.email_verified = True  # they received the email
    user.save(update_fields=["password_hash", "email_verified"])
    force_logout(user)
    return user


# --- one-time email codes (stateless: nothing stored, nothing to clean up) ----
def _otp(purpose, user, window):
    msg = f"{purpose}:{user.id}:{window}:{_fingerprint(user)}"  # the fingerprint kills a reset code once the password changes
    digest = hmac.new(jwt_secret().encode(), msg.encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:4], 'big') % 1_000_000:06d}"


def make_otp(purpose, user):
    return _otp(purpose, user, int(time.time() // OTP_WINDOW))


def check_otp(purpose, user, code):
    if not isinstance(code, str):
        return False
    code, w = code.strip(), int(time.time() // OTP_WINDOW)
    return any(hmac.compare_digest(_otp(purpose, user, x), code) for x in (w, w - 1))


def _user_by_email(email):
    return AppUser.objects.filter(email=normalize_email(email)).exclude(status="deleted").first()


def verify_email_otp(email, code):
    user = _user_by_email(email)
    if not user or not check_otp("verify", user, code):
        raise AuthError("invalid_code", "That code is wrong or has expired.", 400)
    if not user.email_verified:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return user


def reset_token_from_otp(email, code):
    """Trade a correct emailed code for the short-lived token reset_password() needs."""
    user = _user_by_email(email)
    if not user or user.status != "active" or not check_otp("reset", user, code):
        raise AuthError("invalid_code", "That code is wrong or has expired.", 400)
    return make_reset_token(user)


def send_verification(user):
    _mail_code(user, "Your CardSnap verification code", "Verify your email",
               "Enter this code in the CardSnap app to finish creating your account.", make_otp("verify", user))


def send_reset(user):
    _mail_code(user, "Your CardSnap password reset code", "Reset your password",
               "Enter this code in the CardSnap app to choose a new password.", make_otp("reset", user))


def _email_html(heading, intro, code):
    spaced = code  # spacing is CSS only, so a copied code is plain digits
    return f"""<!doctype html><html><body style="margin:0;padding:0;background:#F8FAFC;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F8FAFC;padding:32px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:440px;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:20px;overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<tr><td style="background:#2563EB;padding:24px 28px;color:#FFFFFF;font-size:18px;font-weight:700;letter-spacing:-0.2px;">CardSnap</td></tr>
<tr><td style="padding:32px 28px 8px;color:#0F172A;">
<div style="font-size:22px;font-weight:800;letter-spacing:-0.4px;">{heading}</div>
<div style="font-size:15px;line-height:1.55;color:#5B6B80;margin-top:8px;">{intro}</div></td></tr>
<tr><td align="center" style="padding:20px 28px;">
<div style="background:#EFF6FF;border:1px solid #DBEAFE;border-radius:14px;padding:18px 8px;font-size:34px;font-weight:800;letter-spacing:6px;color:#1D4ED8;font-family:'SF Mono',Menlo,Consolas,monospace;">{spaced}</div></td></tr>
<tr><td style="padding:0 28px 30px;font-size:13px;line-height:1.55;color:#5B6B80;">This code expires in 10 minutes and works once. Never share it with anyone.<br><br>If you didn&rsquo;t ask for this, you can safely ignore this email.</td></tr>
</table>
<div style="font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:12px;color:#94A3B8;margin-top:16px;">Sent by CardSnap</div>
</td></tr></table></body></html>"""


def _mail_code(user, subject, heading, intro, code):
    text = f"{heading}\n\n{intro}\n\nYour code: {code}\n\nIt expires in 10 minutes. Never share it.\nIf you didn't ask for this, ignore this email."
    try:
        msg = EmailMultiAlternatives(subject, text, None, [user.email])
        msg.attach_alternative(_email_html(heading, intro, code), "text/html")
        msg.send()
    except Exception:  # best effort: a mail outage must not change the API response (or leak existence)
        pass

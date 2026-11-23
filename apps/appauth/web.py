import csv
from datetime import datetime, timedelta
from email.utils import parseaddr

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.appauth import mailflare_backend, service
from apps.appauth.models import AppAuthEvent, AppRefreshToken, AppUser, MailLog, MailflareConfig
from apps.core.mixins import CompanyAdminRequiredMixin
from apps.core.pagination import paginate
from apps.dashboards.service import log_activity


SORTS = {"created": "created_at", "-created": "-created_at", "login": "last_login_at", "-login": "-last_login_at"}


def _filtered(request):
    qs = AppUser.objects.all()
    g = request.GET
    if g.get("status") in ("active", "revoked", "deleted"):
        qs = qs.filter(status=g["status"])
    else:
        qs = qs.exclude(status="deleted")
    if g.get("provider") in ("password", "google", "apple"):
        qs = qs.filter(auth_provider=g["provider"])
    q = (g.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(name__icontains=q))
    if g.get("from"):
        qs = qs.filter(created_at__date__gte=g["from"]) if _is_date(g["from"]) else qs
    if g.get("to"):
        qs = qs.filter(created_at__date__lte=g["to"]) if _is_date(g["to"]) else qs
    return qs.order_by(SORTS.get(g.get("sort"), "-created_at"), "-created_at")


def _is_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _stats():
    now = timezone.now()
    today = timezone.localdate()
    live = AppUser.objects.exclude(status="deleted")
    since = lambda d: live.filter(created_at__date__gte=d).count()  # noqa: E731
    by_day = dict(live.filter(created_at__date__gte=today - timedelta(days=29))
                  .annotate(d=TruncDate("created_at")).values_list("d").annotate(n=Count("id")))
    days = [(today - timedelta(days=i)) for i in range(29, -1, -1)]
    series = [{"day": d, "n": by_day.get(d, 0)} for d in days]
    top = max([s["n"] for s in series] + [1])
    for s in series:
        s["pct"] = round(100 * s["n"] / top)
    return {
        "total": live.count(),
        "active_7": live.filter(last_login_at__gte=now - timedelta(days=7)).count(),
        "active_30": live.filter(last_login_at__gte=now - timedelta(days=30)).count(),
        "new_today": since(today),
        "new_week": since(today - timedelta(days=today.weekday())),
        "new_month": since(today.replace(day=1)),
        "google": live.filter(auth_provider="google").count(),
        "password": live.filter(auth_provider="password").count(),
        "revoked": live.filter(status="revoked").count(),
        "google_pct": round(100 * live.filter(auth_provider="google").count() / max(live.count(), 1)),
        "series": series,
    }


class UsersView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        page = paginate(request, _filtered(request))
        keep = request.GET.copy()
        keep.pop("page", None)
        return render(request, "appauth/users.html", {
            "page": page, "stats": _stats(),
            "next_created": "created" if request.GET.get("sort") == "-created" else "-created",
            "next_login": "login" if request.GET.get("sort") == "-login" else "-login", "f": request.GET, "qs": keep.urlencode(),
        })


def _safe_cell(v):
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in "=+-@\t\r" else v  # no spreadsheet formula injection from a user-chosen name


class ExportView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="app-users.csv"'
        w = csv.writer(resp)
        w.writerow(["id", "email", "name", "provider", "status", "email_verified", "created_at", "last_login_at", "revoked_at", "revoked_reason"])
        for u in _filtered(request).iterator():
            w.writerow([_safe_cell(x) for x in (u.id, u.email, u.name, u.auth_provider, u.status, u.email_verified,
                                                u.created_at.isoformat(), u.last_login_at and u.last_login_at.isoformat(),
                                                u.revoked_at and u.revoked_at.isoformat(), u.revoked_reason)])
        return resp


class UserDetailView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        user = get_object_or_404(AppUser, pk=pk)
        sessions = user.refresh_tokens.filter(revoked_at__isnull=True, expires_at__gt=timezone.now()).order_by("-created_at")
        return render(request, "appauth/user_detail.html", {
            "u": user, "events": AppAuthEvent.objects.filter(user=user)[:25], "sessions": sessions,
        })


class UserActionView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk, action):
        user = get_object_or_404(AppUser, pk=pk)
        now = timezone.now()
        if action == "revoke":
            user.status, user.revoked_at = "revoked", now
            user.revoked_reason = (request.POST.get("reason") or "").strip()[:255]
            user.save(update_fields=["status", "revoked_at", "revoked_reason"])
            service.force_logout(user)  # deletes sessions and kills live access tokens
            msg = f"{user.email} revoked."
        elif action == "restore":
            if user.status == "deleted":
                messages.error(request, "A deleted user cannot be restored.")
                return redirect("appauth_web:detail", pk=pk)
            user.status, user.revoked_at, user.revoked_reason = "active", None, ""
            user.save(update_fields=["status", "revoked_at", "revoked_reason"])
            msg = f"{user.email} restored."
        elif action == "logout":
            service.force_logout(user)
            msg = f"{user.email} signed out everywhere."
        elif action == "delete":
            user.status, user.deleted_at = "deleted", now
            user.save(update_fields=["status", "deleted_at"])
            service.force_logout(user)
            msg = f"{user.email} deleted."
        else:
            return HttpResponse(status=404)
        service.log_event(user, {"logout": "force_logout"}.get(action, action), request)
        messages.success(request, msg)
        if action == "delete" or request.POST.get("next") == "list":
            return redirect("appauth_web:users")
        return redirect("appauth_web:detail", pk=pk)


class EmailSettingsView(CompanyAdminRequiredMixin, View):
    """Where an admin enters the Mailflare key. The key is encrypted on the way in and never sent back."""

    def _ctx(self, request, values=None):
        row = MailflareConfig.objects.first()
        try:
            cfg = mailflare_backend.load_config()
        except mailflare_backend.MailflareError as e:
            cfg, broken = None, str(e)
        else:
            broken = ""
        today = timezone.localdate()
        sent = MailLog.objects.filter(status="sent")
        by_day = dict(sent.filter(created_at__date__gte=today - timedelta(days=29)).annotate(d=TruncDate("created_at"))
                      .values_list("d").annotate(n=Count("id")))
        series = [{"day": d, "n": by_day.get(d, 0)} for d in (today - timedelta(days=i) for i in range(29, -1, -1))]
        top = max([x["n"] for x in series] + [1])
        for x in series:
            x["pct"] = round(100 * x["n"] / top)
        mail_stats = {
            "today": sent.filter(created_at__date=today).count(),
            "week": sent.filter(created_at__date__gte=today - timedelta(days=6)).count(),
            "month": sent.filter(created_at__date__gte=today - timedelta(days=29)).count(),
            "total": sent.count(),
            "failed": MailLog.objects.filter(status="failed", created_at__date__gte=today - timedelta(days=29)).count(),
            "series": series,
        }
        default_from = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
        return {
            "mail_stats": mail_stats, "recent": MailLog.objects.all()[:25],
            "row": row, "cfg": cfg, "broken": broken, "default_from": settings.DEFAULT_FROM_EMAIL,
            "mismatch": bool(cfg and cfg.from_address and default_from.lower() != cfg.from_address.lower()),
            "values": values or {"api_url": row.api_url if row else mailflare_backend.DEFAULT_URL,
                                 "mailbox_id": row.mailbox_id if row else "", "from_address": row.from_address if row else ""},
        }

    def get(self, request):
        return render(request, "appauth/email_settings.html", self._ctx(request))

    def post(self, request):
        action = request.POST.get("action", "save")
        if action == "clear":
            MailflareConfig.objects.all().delete()
            log_activity(request.company, "email_settings", "Mailflare key removed", actor=request.user)
            messages.success(request, "Mailflare key removed.")
            return redirect("email_settings")
        if action == "test":
            return self._test(request)
        v = {k: (request.POST.get(k) or "").strip() for k in ("api_url", "mailbox_id", "from_address")}
        key = (request.POST.get("api_key") or "").strip()
        row = MailflareConfig.objects.first()
        errors = []
        if not v["api_url"].startswith("https://"):
            errors.append("The API URL must start with https://")
        if not v["mailbox_id"]:
            errors.append("Enter the mailbox ID")
        if "@" not in v["from_address"]:
            errors.append("Enter the mailbox's email address")
        if not key and not row:
            errors.append("Enter the API key")
        if errors:
            messages.error(request, ". ".join(errors) + ".")
            return render(request, "appauth/email_settings.html", self._ctx(request, v), status=400)
        row = row or MailflareConfig()
        row.api_url, row.mailbox_id, row.from_address, row.updated_by = v["api_url"], v["mailbox_id"], v["from_address"], request.user
        if key:  # a blank key field keeps the saved one
            row.api_key_encrypted = mailflare_backend.encrypt_key(key)
        row.save()
        log_activity(request.company, "email_settings", "Mailflare settings saved", actor=request.user)
        messages.success(request, "Mailflare settings saved. Send a test email to check them.")
        return redirect("email_settings")

    def _test(self, request):
        to = request.user.email
        if not to:
            messages.error(request, "Your account has no email address to send the test to.")
            return redirect("email_settings")
        try:
            send_mail("CardSnap test email", "If you can read this, the CRM can send email through Mailflare.",
                      settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
        except Exception as exc:  # shown to the admin only; the key is never part of these messages
            messages.error(request, f"Test failed: {exc}")
        else:
            messages.success(request, f"Test email sent to {to}.")
        return redirect("email_settings")

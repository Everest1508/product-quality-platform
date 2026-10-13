from urllib.parse import urlencode, urlparse

from django.contrib import messages as dj_messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import service
from apps.accounts.models import ExternalAuthCode, Membership
from apps.core.redirects import safe_next
from apps.uiapi import kudos
from apps.uiapi.tickets import form_errors
from apps.uiapi.views import CompanyAPIView

PER_PAGE = 25
_TAGS = {"success", "error", "info", "warning"}
SORTS = {"name": "user__username", "-name": "-user__username", "role": "role", "-role": "-role", "joined": "created_at", "-joined": "-created_at"}
ROLE_TONE = {"owner": "info", "admin": "warning", "developer": "success", "support": "default", "viewer": "default"}


def _flash(request):
    return [
        {"text": str(m.message), "tags": m.level_tag if m.level_tag in _TAGS else "info"}
        for m in dj_messages.get_messages(request._request)
    ]


def _enforce_csrf(request):
    """DRF checks CSRF only for signed-in sessions. Sign-in is the one write that happens before one,
    so check it by hand: a forged form on another site must not be able to sign a visitor in as someone else."""
    SessionAuthentication().enforce_csrf(request)


class AuthAPIView(APIView):
    """A signed-in person who may not have a company yet (first-run setup)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]


class PublicAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]


class LoginAPIView(PublicAPIView):
    def get(self, request):
        """What the sign-in page needs: where to go after, whether you are already in, and flash messages
        (like "Signed out.") queued by the page you came from."""
        return Response({
            "authenticated": request.user is not None and request.user.is_authenticated,
            "next": safe_next(request.query_params.get("next")) or "",
            "messages": _flash(request),
        })

    def post(self, request):
        _enforce_csrf(request)
        if not hasattr(request.data, "get"):
            return Response({"detail": "Send a JSON object."}, status=400)
        user, error, status = service.sign_in(request._request, request.data.get("username"), request.data.get("password"))
        if user is None:
            return Response({"detail": error, "errors": {"__all__": [error]}}, status=status)
        return Response({"redirect": safe_next(request.data.get("next")) or "/dashboards/"})


def _loopback(redirect_uri):
    try:
        parsed = urlparse(redirect_uri)
    except ValueError:
        return False
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")


class OAuthAuthorizeAPIView(PublicAPIView):
    """Sign-in for a third-party client (the Serop desktop app): on success, the code goes back to the client's
    loopback address. Only loopback addresses are accepted, so this cannot be used as an open redirect."""

    def post(self, request):
        _enforce_csrf(request)
        if not hasattr(request.data, "get"):
            return Response({"detail": "Send a JSON object."}, status=400)
        redirect_uri = request.data.get("redirect_uri", "")
        if not _loopback(redirect_uri):
            return Response({"detail": "redirect_uri must be a loopback (127.0.0.1/localhost) address."}, status=400)
        user, error, status = service.sign_in(request._request, request.data.get("username"), request.data.get("password"), bad_message="Invalid credentials.")
        if user is None:
            return Response({"detail": error, "errors": {"__all__": [error]}}, status=status)
        _obj, raw = ExternalAuthCode.issue(user, request.data.get("client_id", ""), redirect_uri)
        return Response({"redirect": f"{redirect_uri}?{urlencode({'code': raw, 'state': request.data.get('state', '')})}"})


class CompanySetupAPIView(AuthAPIView):
    def post(self, request):
        if request.company:
            return Response({"detail": "You already have a workspace."}, status=400)
        company, form = service.create_company(request._request, request.user, request.data)
        if company is None:
            return Response(form_errors(form), status=400)
        dj_messages.success(request._request, f"Company '{company.name}' created.")
        return Response({"redirect": "/dashboards/", "message": f"Company '{company.name}' created."}, status=201)


def _admin(request):
    if request.company_role not in ("owner", "admin"):
        raise PermissionDenied("Only company admins can perform this action.")


def _name(u):
    return u.get_full_name() or u.username


def member_json(m, request):
    admin = request.company_role in ("owner", "admin")
    return {
        "id": m.pk,
        "user": {"id": m.user_id, "username": m.user.username, "name": _name(m.user), "email": m.user.email,
                 "discord_id": m.user.discord_id, "initial": (m.user.username[:1] or "?").upper(),
                 "first_name": m.user.first_name, "last_name": m.user.last_name},
        "role": m.role, "role_label": m.get_role_display(), "is_leave_approver": m.is_leave_approver,
        "joined": m.created_at.isoformat(),
        "can_edit": admin and m.role != "owner",
        "can_remove": admin and m.role != "owner" and m.user_id != request.user.pk,
        "is_you": m.user_id == request.user.pk,
    }


def _membership(request, pk):
    return get_object_or_404(Membership.objects.select_related("user"), pk=pk, company=request.company)


class TeamListAPIView(CompanyAPIView):
    def get(self, request):
        q = request.query_params
        qs = Membership.objects.filter(company=request.company).select_related("user")
        search = q.get("q", "").strip()
        if search:
            qs = qs.filter(Q(user__username__icontains=search) | Q(user__email__icontains=search)
                           | Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search))
        if q.get("role"):
            qs = qs.filter(role=q["role"])
        page = Paginator(qs.order_by(SORTS.get(q.get("sort", ""), "-role")), PER_PAGE).get_page(q.get("page", 1))
        everyone = Membership.objects.filter(company=request.company)
        return Response({
            "items": [member_json(m, request) for m in page],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
            "counts": {
                "total": everyone.count(), "owner_admin": everyone.filter(role__in=["owner", "admin"]).count(),
                "developer": everyone.filter(role="developer").count(), "support_viewer": everyone.filter(role__in=["support", "viewer"]).count(),
            },
            "roles": [[r.value, r.label] for r in Membership.Role],
            "assignable_roles": [[r.value, r.label] for r in Membership.Role if r.value != "owner"],
            "can_manage": request.company_role in ("owner", "admin"),
        })

    def post(self, request):
        _admin(request)
        membership, form = service.add_member(request.data, request.company, request.user)
        if membership is None:
            return Response(form_errors(form), status=400)
        return Response({"member": member_json(membership, request), "message": f"{membership.user.username} added as {membership.get_role_display()}."}, status=201)


class TeamMemberAPIView(CompanyAPIView):
    def get(self, request, pk):
        """A colleague's page: who they are and the work of theirs this viewer is allowed to see."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.products.access import accessible_tickets

        m = _membership(request, pk)
        admin = request.company_role in ("owner", "admin")
        theirs = accessible_tickets(request.user, request.company).filter(assignees=m.user).select_related("product")
        open_ = theirs.exclude(status__in=["resolved", "closed"]).order_by("-updated_at")
        return Response({
            **member_json(m, request),
            "streak": kudos.on_time_streak(request.company, m.user),
            "milestones": kudos.milestones(request.company, m.user),
            "email": m.user.email if admin else "",
            "stats": {
                "open_tickets": open_.count(),
                "resolved_30d": theirs.filter(status__in=["resolved", "closed"], updated_at__gte=timezone.now() - timedelta(days=30)).count(),
            },
            "tickets": [{"id": t.pk, "key": t.key, "title": t.title, "status": t.get_status_display(), "url": f"/tickets/{t.pk}/"} for t in open_[:10]],
        })

    def patch(self, request, pk):
        _admin(request)
        membership = _membership(request, pk)
        if membership.role == "owner":
            raise PermissionDenied("The owner can't be edited here.")
        saved, form = service.edit_member(request.data, membership, request.company, request.user)
        if saved is None:
            return Response(form_errors(form), status=400)
        saved.refresh_from_db()
        return Response({"member": member_json(saved, request), "message": f"{saved.user.username} updated."})

    def delete(self, request, pk):
        _admin(request)
        membership = _membership(request, pk)
        name = membership.user.username
        error = service.remove_member(membership, request.company, request.user)
        if error:
            return Response({"detail": error}, status=400)
        return Response({"removed": name, "message": f"{name} removed from team."})


class ProfileAPIView(CompanyAPIView):
    def _json(self, request):
        u = request.user
        return {
            "user": {"username": u.username, "name": _name(u), "initial": (u.username[:1] or "?").upper(), "first_name": u.first_name,
                     "last_name": u.last_name, "email": u.email, "discord_id": u.discord_id},
            "role": request.company_role, "role_label": request.company_role.title() if request.company_role else "",
            "company": request.company.name, **self._overview(request),
        }

    @staticmethod
    def _overview(request):
        """What a person would want on their own profile: since when, how busy, what they touched lately."""
        from datetime import timedelta
        from decimal import Decimal

        from django.db.models import Sum
        from django.utils import timezone

        from apps.attendance.models import AttendanceRecord
        from apps.dashboards.models import ActivityLog
        from apps.dsr.duration import format_hm
        from apps.dsr.models import DSREntry
        from apps.products.access import accessible_products, accessible_tickets

        user, company, today = request.user, request.company, timezone.localdate()
        membership = Membership.objects.filter(user=user, company=company).first()
        mine = accessible_tickets(user, company).filter(assignees=user)
        week_start = today - timedelta(days=today.weekday())
        hours = DSREntry.objects.filter(company=company, user=user, date__gte=week_start).aggregate(t=Sum("hours_spent"))["t"] or Decimal("0")
        return {
            "joined": membership.created_at.isoformat() if membership else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "stats": {
                "open_tickets": mine.exclude(status__in=["resolved", "closed"]).count(),
                "resolved_30d": mine.filter(status__in=["resolved", "closed"], updated_at__gte=timezone.now() - timedelta(days=30)).count(),
                "dsr_week": format_hm(hours) if hours else "0m",
                "days_present": AttendanceRecord.objects.filter(company=company, user=user, date__year=today.year, date__month=today.month, check_in__isnull=False).count(),
                "products": accessible_products(user, company).count(),
            },
            "streak": kudos.on_time_streak(company, user),
            "milestones": kudos.milestones(company, user),
            "recent": [
                {"id": a.pk, "title": a.title, "created_at": a.created_at.isoformat(), "url": ""}
                for a in ActivityLog.objects.filter(company=company, actor=user).order_by("-created_at")[:8]
            ],
        }

    def get(self, request):
        return Response(self._json(request))

    def patch(self, request):
        ok, form = service.update_profile(request.data, request.user, request.company)
        if not ok:
            return Response(form_errors(form), status=400)
        return Response({**self._json(request), "message": "Profile updated."})


class NotificationSettingsAPIView(CompanyAPIView):
    """Which kinds of notification this person gets. Applies to every workspace they belong to."""

    def get(self, request):
        from apps.notifications import service as notes

        return Response({"kinds": notes.settings_for(request.user)})

    def put(self, request):
        from apps.notifications import service as notes

        kind, enabled = request.data.get("kind"), bool(request.data.get("enabled"))
        if not notes.set_enabled(request.user, kind, enabled):
            return Response({"detail": "That kind of notification can't be changed."}, status=400)
        label = next(k["label"] for k in notes.settings_for(request.user) if k["kind"] == kind)
        return Response({"kinds": notes.settings_for(request.user), "message": f"{label}: {'on' if enabled else 'off'}."})

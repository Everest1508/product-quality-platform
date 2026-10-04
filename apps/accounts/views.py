import json
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.forms import CompanyCreateForm, LoginForm, ProfileForm, TeamCreateMemberForm, TeamEditForm
from apps.accounts import throttle
from apps.accounts.models import Company, ExternalAccessToken, ExternalAuthCode, Membership
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin, LoginRequiredMixin
from apps.core.redirects import safe_next
from apps.dashboards.service import log_activity

User = get_user_model()


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
    """Sign in, optionally resuming wherever the user was originally headed.

    Login is the one page that is reached *because* something went wrong with
    access, so losing the destination on success is the worst possible time to
    drop it. `?next=` is carried through the POST and validated by
    `safe_next` on the way out, because an unvalidated redirect target is how a
    link with your own domain on it becomes an open redirect.
    """

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return self._render(request, LoginForm(), request.GET.get("next"))

    def post(self, request):
        destination = safe_next(request.POST.get("next"))
        form = LoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            if throttle.is_blocked(request, username_or_email):
                form.add_error(None, throttle.BLOCKED_MESSAGE)
                response = self._render(request, form, request.POST.get("next"))
                response.status_code = 429
                return response
            user = User.objects.filter(email=username_or_email).first()
            if not user:
                user = User.objects.filter(username=username_or_email).first()
            if user:
                authenticated = authenticate(request, username=user.username, password=password)
                if authenticated:
                    throttle.record_success(request, username_or_email)
                    login(request, authenticated)
                    return redirect(destination or "accounts:dashboard")
            throttle.record_failure(request, username_or_email)
            # Deliberately one message for "no such user" and "wrong password".
            # Naming which half was wrong turns the form into a probe for
            # whether an account exists.
            form.add_error(None, "Incorrect username or password.")
        return self._render(request, form, request.POST.get("next"))

    def _render(self, request, form, next_url):
        """One place that builds the login context, for GET and for failed POST.

        The bound form carries the typed username back into the field, so a
        mistake in the password does not also mean retyping the email.
        """
        return render(request, "accounts/login.html", {
            "form": form,
            "next": safe_next(next_url) or "",
        })


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "Signed out.")
        return redirect("accounts:login")


class DashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return redirect("dashboards:index")


class CompanySwitchView(LoginRequiredMixin, View):
    def post(self, request):
        company_id = request.POST.get("company_id")
        membership = Membership.objects.filter(
            user=request.user,
            company_id=company_id,
        ).first()
        if not membership:
            messages.error(request, "Workspace not found.")
        else:
            request.session[settings.ACTIVE_COMPANY_SESSION_KEY] = membership.company_id
            messages.success(request, f"Switched to {membership.company.name}.")
        return redirect("accounts:dashboard")


class CompanySetupView(LoginRequiredMixin, View):
    def get(self, request):
        if request.company:
            return redirect("accounts:dashboard")
        return render(request, "accounts/company_setup.html", {"form": CompanyCreateForm()})

    def post(self, request):
        form = CompanyCreateForm(request.POST)
        if form.is_valid():
            company = form.save()
            membership = Membership.objects.create(
                user=request.user,
                company=company,
                role=Membership.Role.OWNER,
            )
            request.session[settings.ACTIVE_COMPANY_SESSION_KEY] = membership.company_id
            messages.success(request, f"Company '{company.name}' created.")
            return redirect("accounts:dashboard")
        return render(request, "accounts/company_setup.html", {"form": form})


TEAM_SORT_MAP = {
    "name": "user__username",
    "-name": "-user__username",
    "role": "role",
    "-role": "-role",
    "joined": "created_at",
    "-joined": "-created_at",
}


class TeamListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = Membership.objects.filter(company=request.company).select_related("user")

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search)
            )

        role = request.GET.get("role")
        if role:
            qs = qs.filter(role=role)

        sort = request.GET.get("sort", "-role")
        order = TEAM_SORT_MAP.get(sort, "-role")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        form = TeamCreateMemberForm(company=request.company)

        all_memberships = Membership.objects.filter(company=request.company)
        total_count = all_memberships.count()
        owner_admin_count = all_memberships.filter(role__in=["owner", "admin"]).count()
        developer_count = all_memberships.filter(role="developer").count()
        support_viewer_count = all_memberships.filter(role__in=["support", "viewer"]).count()
        view_mode = request.GET.get("view", "grid")

        if request.headers.get("HX-Request") == "true":
            return render(request, "accounts/partials/_team_list_body.html", {
                "page": page,
                "memberships": page,
                "view_mode": view_mode,
            })

        return render(request, "accounts/team_list.html", {
            "page": page,
            "memberships": page,
            "form": form,
            "search": search,
            "current_role": role,
            "current_sort": sort,
            "view_mode": view_mode,
            "total_count": total_count,
            "owner_admin_count": owner_admin_count,
            "developer_count": developer_count,
            "support_viewer_count": support_viewer_count,
        })


class TeamInviteView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = TeamCreateMemberForm(request.POST, company=request.company)

        if form.is_valid():
            membership = form.save()
            log_activity(
                request.company, "member_joined",
                f"{membership.user.username} joined the team",
                description=f"Added as {membership.get_role_display()}",
                actor=request.user,
                target_content_type="membership",
                target_object_id=membership.pk,
            )
            messages.success(request, f"{membership.user.username} added as {membership.get_role_display()}.")
            return redirect("accounts:team_list")

        memberships = (
            Membership.objects.filter(company=request.company)
            .select_related("user")
            .order_by("-role", "user__username")
        )
        paginator = Paginator(memberships, 25)
        page = paginator.get_page(request.GET.get("page", 1))
        return render(request, "accounts/team_list.html", {
            "page": page,
            "memberships": page,
            "form": form,
            "show_invite_modal": True,
        })


class TeamRemoveView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        membership = Membership.objects.filter(pk=pk, company=request.company).first()
        if not membership:
            messages.error(request, "Member not found.")
            return redirect("accounts:team_list")
        if membership.user == request.user:
            messages.error(request, "You cannot remove yourself.")
            return redirect("accounts:team_list")
        if membership.role == Membership.Role.OWNER:
            messages.error(request, "Cannot remove the owner.")
            return redirect("accounts:team_list")

        username = membership.user.username
        membership.delete()
        log_activity(
            request.company, "member_removed",
            f"{username} removed from team",
            actor=request.user,
            target_content_type="membership",
            target_object_id=pk,
        )
        messages.success(request, f"{username} removed from team.")

        if request.headers.get("HX-Request") == "true":
            return HttpResponse("")
        return redirect("accounts:team_list")


class TeamEditView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        membership = Membership.objects.select_related("user").filter(pk=pk, company=request.company).first()
        if not membership:
            messages.error(request, "Member not found.")
            return redirect("accounts:team_list")
        form = TeamEditForm(membership=membership, initial={
            "first_name": membership.user.first_name,
            "last_name": membership.user.last_name,
            "email": membership.user.email,
            "discord_id": membership.user.discord_id,
            "role": membership.role,
        })
        if request.headers.get("HX-Request") == "true":
            return render(request, "accounts/partials/_edit_member_form.html", {
                "form": form, "membership": membership,
            })
        return redirect("accounts:team_list")

    def post(self, request, pk):
        membership = Membership.objects.select_related("user").filter(pk=pk, company=request.company).first()
        if not membership:
            messages.error(request, "Member not found.")
            return redirect("accounts:team_list")
        form = TeamEditForm(request.POST, membership=membership)
        if form.is_valid():
            old_role = membership.role
            membership = form.save()
            if membership.role != old_role:
                log_activity(
                    request.company, "member_role_changed",
                    f"{membership.user.username} role changed",
                    description=f"{old_role} → {membership.role}",
                    actor=request.user,
                    target_content_type="membership",
                    target_object_id=membership.pk,
                    metadata={"from": old_role, "to": membership.role},
                )
            messages.success(request, f"{membership.user.username} updated.")
            if request.headers.get("HX-Request") == "true":
                return render(request, "accounts/partials/_team_member_row.html", {
                    "membership": membership,
                })
            return redirect("accounts:team_list")
        if request.headers.get("HX-Request") == "true":
            return render(request, "accounts/partials/_edit_member_form.html", {
                "form": form, "membership": membership,
            }, status=422)
        return redirect("accounts:team_list")


class ProfileView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = ProfileForm(instance=request.user)
        return render(request, "accounts/profile.html", {"form": form})

    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
        return render(request, "accounts/profile.html", {"form": form})


class OAuthAuthorizeView(View):
    """External sign-in entry point for third-party clients (currently just the
    Serop desktop app). Loopback-only redirect_uri to keep this from being usable
    as an open redirect."""

    def get(self, request):
        client_id = request.GET.get("client_id", "")
        redirect_uri = request.GET.get("redirect_uri", "")
        state = request.GET.get("state", "")
        if not _is_loopback_redirect(redirect_uri):
            return HttpResponseBadRequest("redirect_uri must be a loopback (127.0.0.1/localhost) address.")

        if request.user.is_authenticated:
            return self._issue_and_redirect(request.user, client_id, redirect_uri, state)

        return render(request, "accounts/oauth_authorize.html", {
            "form": LoginForm(),
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        })

    def post(self, request):
        client_id = request.POST.get("client_id", "")
        redirect_uri = request.POST.get("redirect_uri", "")
        state = request.POST.get("state", "")
        if not _is_loopback_redirect(redirect_uri):
            return HttpResponseBadRequest("redirect_uri must be a loopback (127.0.0.1/localhost) address.")

        form = LoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            if throttle.is_blocked(request, username_or_email):
                form.add_error(None, throttle.BLOCKED_MESSAGE)
                return render(request, "accounts/oauth_authorize.html", {
                    "form": form, "client_id": client_id, "redirect_uri": redirect_uri, "state": state,
                }, status=429)
            user = User.objects.filter(email=username_or_email).first() or User.objects.filter(username=username_or_email).first()
            authenticated = authenticate(request, username=user.username, password=password) if user else None
            if authenticated:
                throttle.record_success(request, username_or_email)
                login(request, authenticated)
                return self._issue_and_redirect(authenticated, client_id, redirect_uri, state)
            throttle.record_failure(request, username_or_email)
            form.add_error(None, "Invalid credentials.")

        return render(request, "accounts/oauth_authorize.html", {
            "form": form,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        })

    def _issue_and_redirect(self, user, client_id, redirect_uri, state):
        _code_obj, raw_code = ExternalAuthCode.issue(user, client_id, redirect_uri)
        query = urlencode({"code": raw_code, "state": state})
        return redirect(f"{redirect_uri}?{query}")


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

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.forms import CompanyCreateForm, LoginForm, ProfileForm, TeamCreateMemberForm, TeamEditForm
from apps.accounts.models import Company, Membership
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin, LoginRequiredMixin
from apps.dashboards.service import log_activity

User = get_user_model()


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return render(request, "accounts/login.html", {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = User.objects.filter(email=username_or_email).first()
            if not user:
                user = User.objects.filter(username=username_or_email).first()
            if user:
                authenticated = authenticate(request, username=user.username, password=password)
                if authenticated:
                    login(request, authenticated)
                    return redirect("accounts:dashboard")
            form.add_error(None, "Invalid credentials.")
        return render(request, "accounts/login.html", {"form": form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "Signed out.")
        return redirect("accounts:login")


class DashboardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        return redirect("dashboards:index")


class CompanySetupView(LoginRequiredMixin, View):
    def get(self, request):
        if request.company:
            return redirect("accounts:dashboard")
        return render(request, "accounts/company_setup.html", {"form": CompanyCreateForm()})

    def post(self, request):
        form = CompanyCreateForm(request.POST)
        if form.is_valid():
            company = form.save()
            Membership.objects.create(
                user=request.user,
                company=company,
                role=Membership.Role.OWNER,
            )
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

        if request.headers.get("HX-Request") == "true":
            return render(request, "accounts/partials/_team_list_body.html", {
                "page": page,
            })

        return render(request, "accounts/team_list.html", {
            "page": page,
            "memberships": page,
            "form": form,
            "search": search,
            "current_role": role,
            "current_sort": sort,
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

"""Account and team actions with their side effects, shared by the JSON API.
Access checks stay with the caller."""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login

from apps.accounts import throttle
from apps.accounts.forms import CompanyCreateForm, ProfileForm, TeamCreateMemberForm, TeamEditForm
from apps.accounts.models import Membership
from apps.dashboards.service import log_activity

User = get_user_model()
BAD_LOGIN = "Incorrect username or password."


def sign_in(request, username_or_email, password, bad_message=BAD_LOGIN):
    """Check the credentials and start a session. Returns (user, error, status).

    One message for "no such user" and "wrong password": naming which half was wrong turns
    the form into a probe for whether an account exists. Failures are counted per (IP, name)."""
    username_or_email = (username_or_email or "").strip()
    if not username_or_email or not password:
        return None, "Enter your username and password.", 400
    if throttle.is_blocked(request, username_or_email):
        return None, throttle.BLOCKED_MESSAGE, 429
    user = User.objects.filter(email=username_or_email).first() or User.objects.filter(username=username_or_email).first()
    authenticated = authenticate(request, username=user.username, password=password) if user else None
    if authenticated:
        throttle.record_success(request, username_or_email)
        login(request, authenticated)
        return authenticated, "", 200
    throttle.record_failure(request, username_or_email)
    return None, bad_message, 400


def create_company(request, user, data):
    """First-run setup: a company with the person as its owner. Returns (company, form)."""
    form = CompanyCreateForm(data)
    if not form.is_valid():
        return None, form
    from apps.accounts.models import Membership as M

    company = form.save()
    membership = M.objects.create(user=user, company=company, role=M.Role.OWNER)
    request.session[settings.ACTIVE_COMPANY_SESSION_KEY] = membership.company_id
    log_activity(
        company, "company_created", f"Company '{company.name}' created",
        description=f"{user.get_full_name() or user.username} set up the workspace", actor=user,
    )
    return company, form


def add_member(data, company, actor):
    """Returns (membership, form); membership is None when the form is invalid."""
    form = TeamCreateMemberForm(data, company=company)
    if not form.is_valid():
        return None, form
    membership = form.save()
    log_activity(
        company, "member_joined", f"{membership.user.username} joined the team",
        description=f"Added as {membership.get_role_display()}", actor=actor,
        target_content_type="membership", target_object_id=membership.pk,
    )
    return membership, form


def edit_member(data, membership, company, actor):
    """Returns (membership, form); membership is None when the form is invalid."""
    form = TeamEditForm(data, membership=membership)
    if not form.is_valid():
        return None, form
    old_role = membership.role
    membership = form.save()
    if membership.role != old_role:
        log_activity(
            company, "member_role_changed", f"{membership.user.username} role changed",
            description=f"{old_role} → {membership.role}", actor=actor,
            target_content_type="membership", target_object_id=membership.pk,
            metadata={"from": old_role, "to": membership.role},
        )
    return membership, form


def remove_member(membership, company, actor):
    """Returns an error message, or None. Nobody removes themselves or the owner."""
    if membership.user_id == actor.pk:
        return "You cannot remove yourself."
    if membership.role == Membership.Role.OWNER:
        return "Cannot remove the owner."
    username, pk = membership.user.username, membership.pk
    membership.delete()
    log_activity(
        company, "member_removed", f"{username} removed from team", actor=actor,
        target_content_type="membership", target_object_id=pk,
    )
    return None


def update_profile(data, user, company):
    form = ProfileForm(data, instance=user)
    if not form.is_valid():
        return False, form
    form.save()
    if form.changed_data:
        log_activity(company, "profile_updated", "Profile updated", description=", ".join(form.changed_data), actor=user)
    return True, form

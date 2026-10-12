from django.conf import settings
from django.contrib import messages

from apps.accounts.models import Membership


def activate_company(request, company_id):
    """Make `company_id` the active workspace for this session if the user is a
    member. The one place a session switches company, shared by the classic view
    and the JSON API."""
    try:
        membership = (
            Membership.objects.select_related("company")
            .filter(user=request.user, company_id=int(company_id))
            .first()
        )
    except (TypeError, ValueError):
        membership = None
    if not membership:
        messages.error(request, "Workspace not found.")
        return None
    request.session[settings.ACTIVE_COMPANY_SESSION_KEY] = membership.company_id
    messages.success(request, f"Switched to {membership.company.name}.")
    return membership

from django.conf import settings

from apps.accounts.models import Membership


class CurrentCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.company_role = None

        if request.user.is_authenticated:
            memberships = list(
                Membership.objects.select_related("company")
                .filter(user=request.user)
            )
            if memberships:
                active_id = request.session.get(settings.ACTIVE_COMPANY_SESSION_KEY)
                membership = next(
                    (m for m in memberships if m.company_id == active_id),
                    memberships[0],
                )
                request.company = membership.company
                request.company_role = membership.role

        response = self.get_response(request)
        return response

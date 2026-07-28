from apps.accounts.models import Membership


class CurrentCompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        request.company_role = None

        if request.user.is_authenticated:
            membership = (
                Membership.objects.select_related("company")
                .filter(user=request.user)
                .first()
            )
            if membership:
                request.company = membership.company
                request.company_role = membership.role

        response = self.get_response(request)
        return response

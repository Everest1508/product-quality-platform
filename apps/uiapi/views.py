from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications import service

LIMIT = 100


class CompanyAPIView(APIView):
    """Session-cookie JSON view. CSRF is enforced on writes by SessionAuthentication.
    Every subclass works on `request.company`, set by CurrentCompanyMiddleware."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.company:
            raise PermissionDenied("No active company.")


class NotificationListView(CompanyAPIView):
    def get(self, request):
        rows = service.mine(request.user, request.company)
        if request.query_params.get("filter") == "unread":
            rows = rows.filter(read_at__isnull=True)
        items = [{**n.as_json(), "kind_label": n.get_kind_display()} for n in rows[:LIMIT]]
        return Response({"unread": service.unread_count(request.user, request.company), "items": items})


class NotificationReadAllView(CompanyAPIView):
    def post(self, request):
        service.mark_read(request.user, request.company)
        return Response({"unread": 0})

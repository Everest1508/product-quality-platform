"""JSON API for the DSR MCP server (repo: dsr-mcp). Mounted at /api/v1/.

The CRM stays the source of truth: every rule the web sheet applies (submission
window, hours cap, product access) is applied here by reusing the same form and
service code. A token only works here if it was issued to client_id "dsr-mcp".
"""
from datetime import datetime

from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ExternalAccessToken, Membership
from apps.dsr.forms import DSREntryForm
from apps.dsr.models import DSREntry
from apps.dsr.service import submission_window, suggestions
from apps.dsr.views import _is_privileged
from apps.products.access import accessible_products, accessible_tickets

CLIENT_ID = "dsr-mcp"


class DSRTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            raise AuthenticationFailed("Missing or invalid Authorization header. Use: Bearer <token>")
        token = ExternalAccessToken.validate(header[7:].strip())
        if not token or token.client_id != CLIENT_ID:
            raise AuthenticationFailed("Invalid or revoked token.")
        return (token.user, token)


class DSRAPIView(APIView):
    authentication_classes = [DSRTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # ponytail: first membership unless ?company=<id> names another one the
        # user belongs to. Add a company picker if people join several workspaces.
        memberships = Membership.objects.filter(user=request.user).select_related("company").order_by("id")
        wanted = request.query_params.get("company")
        membership = memberships.filter(company_id=wanted).first() if wanted and wanted.isdigit() else None
        membership = membership or memberships.first()
        if membership is None:
            raise AuthenticationFailed("This user belongs to no company.")
        self.company, self.role = membership.company, membership.role


def _day(raw):
    if not raw:
        return timezone.localdate(), None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "date must be YYYY-MM-DD."


def _entry(e):
    return {
        "id": e.pk,
        "date": e.date.isoformat(),
        "task_name": e.task_name,
        "product": e.product_id,
        "ticket": e.ticket_id,
        "category": e.category,
        "status": e.status,
        "hours_spent": str(e.hours_spent),
        "notes": e.notes,
        "source": e.source,
        "source_id": e.source_id,
        "is_auto_logged": e.is_auto_logged,
    }


class MeView(DSRAPIView):
    def get(self, request):
        u = request.user
        return Response({
            "id": u.pk,
            "username": u.username,
            "name": u.get_full_name() or u.username,
            "email": u.email,
            "company": {"id": self.company.pk, "name": self.company.name},
            "role": self.role,
            "today": timezone.localdate().isoformat(),
        })


class ProjectsView(DSRAPIView):
    def get(self, request):
        products = accessible_products(request.user, self.company).order_by("name")
        return Response([{"id": p.pk, "key": p.key, "name": p.name} for p in products])


class TodayView(DSRAPIView):
    """The day's DSR entries (today unless ?date=) and whether the day still takes writes."""

    def get(self, request):
        day, err = _day(request.query_params.get("date"))
        if err:
            return Response({"error": err}, status=400)
        entries = DSREntry.objects.filter(company=self.company, user=request.user, date=day)
        can_edit, reason = submission_window(day, _is_privileged(request.user, self.company))
        return Response({
            "date": day.isoformat(),
            "exists": entries.exists(),
            "can_edit": can_edit,
            "locked_reason": reason,
            "total_hours": str(sum((e.hours_spent for e in entries), 0)),
            "entries": [_entry(e) for e in entries],
        })


class ActivitiesView(DSRAPIView):
    """CRM-side activity: tickets the person touched or has in progress, not yet in the DSR."""

    def get(self, request):
        day, err = _day(request.query_params.get("date"))
        if err:
            return Response({"error": err}, status=400)
        rows = suggestions(self.company, request.user, day, limit=50)
        return Response([{
            "activity": f"{r['key']} {r['title']}: {r['did']}",
            "project": r["product"],
            "source": "crm_ticket",
            "source_id": r["key"],
            "ticket": r["number"],
            "timestamp": r["last"].isoformat() if r["last"] else None,
            "suggested_hours": str(r["hours"]),
            "category": r["category"],
            "status": r["status"],
        } for r in rows])


def _form_data(body, entry=None):
    """The posted fields, falling back to the stored entry so a PUT can send only what changed."""
    keep = {
        "task_name": entry.task_name, "product": entry.product_id or "", "category": entry.category,
        "hours_spent": entry.hours_spent, "status": entry.status, "notes": entry.notes,
    } if entry else {}
    data = {k: body.get(k, keep.get(k)) for k in ("task_name", "product", "category", "hours_spent", "status", "notes")}
    return {k: ("" if v is None else v) for k, v in data.items()}


class DSRCreateView(DSRAPIView):
    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        day, err = _day(body.get("date"))
        if err:
            return Response({"error": err}, status=400)
        can_edit, reason = submission_window(day, _is_privileged(request.user, self.company))
        if not can_edit:
            return Response({"error": reason}, status=403)

        ticket = None
        if body.get("ticket"):
            ticket = accessible_tickets(request.user, self.company).filter(pk=str(body["ticket"])).first() \
                if str(body["ticket"]).isdigit() else None
            if ticket is None:
                return Response({"error": "Unknown ticket."}, status=400)
        source, source_id = str(body.get("source", ""))[:32], str(body.get("source_id", ""))[:128]

        mine = DSREntry.objects.filter(company=self.company, user=request.user, date=day)
        task = str(body.get("task_name", "")).strip()
        existing = (
            (ticket and mine.filter(ticket=ticket).first())
            or (source_id and mine.filter(source=source, source_id=source_id).first())
            or (task and mine.filter(task_name__iexact=task).first())
        )
        if existing:
            return Response(
                {"error": "This is already in today's DSR. Use PUT to change it.", "existing": _entry(existing)},
                status=status.HTTP_409_CONFLICT,
            )

        products = accessible_products(request.user, self.company)
        data = _form_data(body)
        if ticket and not data["product"] and ticket.product_id:
            data["product"] = ticket.product_id
        form = DSREntryForm(data, products=products)
        if not form.is_valid():
            return Response({"error": "Invalid entry.", "fields": form.errors.get_json_data()}, status=400)
        entry = form.save(commit=False)
        entry.company, entry.user, entry.date = self.company, request.user, day
        entry.ticket, entry.source, entry.source_id = ticket, source, source_id
        entry.is_auto_logged = False
        entry.save()
        return Response(_entry(entry), status=status.HTTP_201_CREATED)


class DSRDetailView(DSRAPIView):
    def put(self, request, pk):
        # Own entries only: a missing entry and someone else's both answer 404.
        entry = DSREntry.objects.filter(pk=pk, company=self.company, user=request.user).first()
        if entry is None:
            return Response({"error": "Not found."}, status=404)
        can_edit, reason = submission_window(entry.date, _is_privileged(request.user, self.company))
        if not can_edit:
            return Response({"error": reason}, status=403)
        body = request.data if isinstance(request.data, dict) else {}
        form = DSREntryForm(
            _form_data(body, entry), instance=entry, products=accessible_products(request.user, self.company)
        )
        if not form.is_valid():
            return Response({"error": "Invalid entry.", "fields": form.errors.get_json_data()}, status=400)
        form.save()
        return Response(_entry(entry))

    patch = put

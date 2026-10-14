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
from django.db.models import Q
from django.utils.text import slugify

from apps.dashboards.service import log_activity
from apps.products.access import accessible_products, accessible_tickets
from apps.products.forms import ProductCreateForm
from apps.products.models import Product
from apps.products.webhook import notify_ticket_created
from apps.tickets.models import Ticket

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


def _attendance(company, user, day):
    """The day's real worked time from the punch card, or None if they did not punch in.

    `net_minutes` is what attendance itself reports (an open day counts elapsed time, capped at
    the shift, less the unpaid break), so a DSR built from it agrees with the attendance page.
    """
    from apps.attendance.models import AttendanceRecord
    from apps.attendance.service import net_minutes_for, shift_for

    record = AttendanceRecord.objects.filter(company=company, user=user, date=day).first()
    if record is None or record.check_in is None:
        return None
    return {
        "check_in": timezone.localtime(record.check_in).isoformat(),
        "check_out": timezone.localtime(record.check_out).isoformat() if record.check_out else None,
        "net_minutes": net_minutes_for(record, shift_for(company)),
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
            "can_create_projects": self.role in (Membership.Role.OWNER, Membership.Role.ADMIN),
            "today": timezone.localdate().isoformat(),
        })


class ProjectsView(DSRAPIView):
    def get(self, request):
        products = accessible_products(request.user, self.company).order_by("name")
        return Response([{"id": p.pk, "key": p.key, "name": p.name} for p in products])

    def post(self, request):
        return _create_project(self, request)


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
            "attendance": _attendance(self.company, request.user, day),
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
            # Real activity times, so a client can measure time instead of guessing it.
            "events": [t.isoformat() for t in r["events"]],
            "touched": r["touched"],
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


def _ticket(t, user):
    return {
        "id": t.pk,
        "key": t.key,
        "title": t.title,
        "product": t.product_id,
        "product_name": t.product.name if t.product_id else "",
        "status": t.status,
        "ticket_type": t.ticket_type,
        "priority": t.priority,
        "assigned_to_me": any(a.pk == user.pk for a in t.assignees.all()),
        "url": f"/tickets/{t.pk}/",
    }


def _open(qs):
    return qs.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])


class TicketsView(DSRAPIView):
    def get(self, request):
        qs = accessible_tickets(request.user, self.company).select_related("product").prefetch_related("assignees")
        if request.query_params.get("status", "open") != "all":
            qs = _open(qs)
        product = request.query_params.get("product")
        if product:
            qs = qs.filter(product_id=product) if product.isdigit() else qs.none()
        q = request.query_params.get("q", "").strip()
        if q:
            cond = Q(title__icontains=q)
            # "AUM-014" is not stored: match the product key and number parts instead.
            key, _, num = q.rpartition("-")
            if key and num.isdigit():
                cond |= Q(product__key__iexact=key, number=int(num))
            else:
                cond |= Q(product__key__icontains=q)
            qs = qs.filter(cond)
        return Response([_ticket(t, request.user) for t in qs.order_by("-created_at", "-pk")[:20]])

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        errors = {}
        title = str(body.get("title") or "").strip()
        if not title:
            errors["title"] = "Title is required."
        elif len(title) > 255:
            errors["title"] = "Title can be at most 255 characters."
        product = None
        pid = str(body.get("product") or "")
        if pid.isdigit():
            product = accessible_products(request.user, self.company).filter(pk=pid).first()
        if product is None:
            errors["product"] = "Unknown project, or you do not have access to it. Pick one from your projects."
        choices = {
            "ticket_type": (Ticket.TicketType, Ticket.TicketType.BUG),
            "priority": (Ticket.Priority, Ticket.Priority.MEDIUM),
            "status": (Ticket.Status, Ticket.Status.OPEN),
        }
        vals = {}
        for name, (enum, default) in choices.items():
            raw = body.get(name)
            vals[name] = str(raw) if raw not in (None, "") else default.value
            if vals[name] not in enum.values:
                errors[name] = f"Must be one of: {', '.join(enum.values)}."
        assign = body.get("assign_to_me", True)
        if isinstance(assign, str):
            assign = assign.strip().lower() not in ("false", "0", "no", "")
        if errors:
            return Response({"error": "Invalid ticket.", "fields": errors}, status=400)

        dup = _open(accessible_tickets(request.user, self.company)).filter(
            product=product, title__iexact=title
        ).select_related("product").prefetch_related("assignees").first()
        if dup:
            return Response(
                {"error": f"An open ticket with this title already exists ({dup.key}).", "existing": _ticket(dup, request.user)},
                status=status.HTTP_409_CONFLICT,
            )

        finished = vals["status"] in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED)
        ticket = Ticket(
            company=self.company, created_by=request.user, source="manual", product=product,
            title=title, description=str(body.get("description") or ""),
            ticket_type=vals["ticket_type"], priority=vals["priority"],
            status=Ticket.Status.OPEN if finished else vals["status"],
        )
        ticket.save()
        ticket.set_assignees([request.user] if assign else [], actor=request.user)
        notify_ticket_created(ticket)
        log_activity(
            self.company, "ticket_created", f"Ticket {ticket.key} created",
            description=ticket.title, actor=request.user,
            target_content_type="ticket", target_object_id=ticket.pk,
            metadata={"product_id": ticket.product_id},
        )
        if finished:
            # The model's transition runs the side effects, including the DSR entry.
            ticket.transition_to(vals["status"], actor=request.user)
        ticket = Ticket.objects.select_related("product").prefetch_related("assignees").get(pk=ticket.pk)
        return Response(_ticket(ticket, request.user), status=status.HTTP_201_CREATED)


# POST /v1/projects/, called from ProjectsView.post
def _create_project(self, request):
    if self.role not in (Membership.Role.OWNER, Membership.Role.ADMIN):
        return Response(
            {"error": "Only an owner or admin can create a project. Ask one of them to create it."}, status=403
        )
    body = request.data if isinstance(request.data, dict) else {}
    name = str(body.get("name") or "").strip()
    key = str(body.get("key") or "").strip().upper()
    mine = Product.objects.filter(company=self.company)
    clash = None
    if name:
        clash = mine.filter(Q(name__iexact=name) | Q(slug=slugify(name))).first()
    if key and not clash:
        clash = mine.filter(key=key).first()
    if clash:
        return Response(
            {"error": f"A project named {clash.name} ({clash.key}) already exists.",
             "existing": {"id": clash.pk, "key": clash.key, "name": clash.name}},
            status=status.HTTP_409_CONFLICT,
        )
    form = ProductCreateForm({"name": name, "key": key, "default_environment": "production"}, company=self.company)
    if not form.is_valid():
        return Response({"error": "Invalid project.", "fields": form.errors.get_json_data()}, status=400)
    product = form.save()
    log_activity(
        self.company, "product_created", f"Product '{product.name}' created",
        actor=request.user, target_content_type="product", target_object_id=product.pk,
    )
    return Response({"id": product.pk, "key": product.key, "name": product.name}, status=status.HTTP_201_CREATED)

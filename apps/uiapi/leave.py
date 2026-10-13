import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.icons import ICON_CHOICES
from apps.leave import actions, service
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.uiapi.tickets import form_errors
from apps.uiapi.views import CompanyAPIView


def _admin(request):
    if request.company_role not in ("owner", "admin"):
        raise PermissionDenied("Only company admins can perform this action.")


def _approver(request):
    if not actions.is_approver(request.user, request.company):
        raise PermissionDenied("Only leave approvers can do this.")


def _name(u):
    return u.get_full_name() or u.username


def _num(v):
    return None if v is None else str(v)


def _d1(v):
    """Half-day precision, always one decimal ("3.0"), whatever the arithmetic left behind."""
    return str(Decimal(v).quantize(Decimal("0.1")))


def balance_json(b):
    return {
        "policy": {"id": b["policy"].pk, "name": b["policy"].name, "color": b["policy"].color, "icon": b["policy"].icon, "is_paid": b["policy"].is_paid},
        "unlimited": b["is_unlimited"], "limit_label": b["limit_label"], "approved_label": b["approved_label"], "pending_label": b["pending_label"],
        "remaining_label": b["remaining_label"], "has_pending": b["has_pending"],
        "used_pct": 0 if b["is_unlimited"] or not b["limit"] else min(100, round(float(b["approved"]) * 100 / float(b["limit"]))),
    }


def request_json(r, **extra):
    return {
        "id": r.pk, "policy": {"id": r.policy_id, "name": r.policy.name, "color": r.policy.color}, "start": r.start_date.isoformat(), "end": r.end_date.isoformat(),
        "span": r.span_label, "days": str(r.days), "days_label": r.days_label, "is_half_day": r.is_half_day, "status": r.status, "status_label": r.get_status_display(),
        "reason": r.reason, "split_label": r.split_label, "paid": str(r.split["paid"]), "unpaid": str(r.split["unpaid"]), "split_mode": r.split_mode,
        "decision_note": r.decision_note, "decided_by": _name(r.decided_by) if r.decided_by_id else "",
        "created_at": r.created_at.isoformat(), "can_cancel": r.is_pending, **extra,
    }


def _year(request):
    try:
        return int(request.query_params["year"])
    except (KeyError, TypeError, ValueError):
        return timezone.localdate().year


class MyLeaveAPIView(CompanyAPIView):
    def get(self, request):
        year = _year(request)
        reqs = LeaveRequest.objects.filter(company=request.company, user=request.user).select_related("policy", "decided_by").order_by("-created_at")
        return Response({
            "year": year, "can_approve": actions.is_approver(request.user, request.company),
            "balances": [balance_json(b) for b in service.balances_for(request.company, request.user, year)],
            "requests": [request_json(r) for r in reqs],
        })


class ApplyAPIView(CompanyAPIView):
    def get(self, request):
        today = timezone.localdate()
        return Response({
            "today": today.isoformat(),
            "policies": [{"id": p.pk, "name": p.name, "color": p.color, "icon": p.icon, "is_paid": p.is_paid} for p in service.policies_for(request.company)],
            "balances": [balance_json(b) for b in service.balances_for(request.company, request.user)],
        })

    def post(self, request):
        leave, form = actions.apply_for_leave(request.company, request.user, request.data)
        if leave is None:
            return Response(form_errors(form), status=400)
        return Response({"id": leave.pk, "message": "Leave request submitted for approval."}, status=201)


class SplitPreviewAPIView(CompanyAPIView):
    """What the dates would be charged as, before anything is saved. A half-typed range is the normal state of the
    form, so anything unusable answers with an empty preview rather than an error."""

    def post(self, request):
        d = request.data
        empty = Response({"preview": None})
        policy_id, start = d.get("policy_id"), d.get("start_date")
        end = d.get("end_date") or start
        if not (policy_id and start):
            return empty
        try:
            policy = LeavePolicy.objects.get(pk=policy_id, company=request.company)
            first, last = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
            if last < first:
                return empty
            days = Decimal("0.5") if d.get("is_half_day") else service.working_days(first, last)
            if days <= 0:
                return empty
            result = service.auto_split(request.company, request.user, policy, first, last, days)
        except (LeavePolicy.DoesNotExist, ValueError, TypeError, ValidationError):
            return empty
        clash = service.clash_for(request.company, request.user, first, last)
        return Response({"preview": {
            "days": _d1(days), "days_label": service.format_days(days), "paid": _d1(result["paid"]), "unpaid": _d1(result["unpaid"]),
            "paid_label": service.format_days(result["paid"]), "unpaid_label": service.format_days(result["unpaid"]), "reasons": result["reasons"],
            "clash_people": clash["people"], "clash_text": service.clash_sentence(clash), "policy": policy.name,
        }})


class CancelAPIView(CompanyAPIView):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest.objects.select_related("policy", "user"), pk=pk, company=request.company, user=request.user)
        error = actions.cancel_request(request.company, request.user, leave)
        if error:
            return Response({"detail": error}, status=400)
        return Response({"message": "Leave request withdrawn."})


class CalendarAPIView(CompanyAPIView):
    def get(self, request):
        today = timezone.localdate()
        year, month = today.year, today.month
        parts = (request.query_params.get("month") or "").strip().split("-")
        if len(parts) == 2 and all(p.isdigit() for p in parts) and 1 <= int(parts[1]) <= 12 and 1900 <= int(parts[0]) <= 2200:
            year, month = int(parts[0]), int(parts[1])
        show_types = actions.is_approver(request.user, request.company)
        cal = service.month_calendar(request.company, year, month, show_types=show_types)
        py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)

        def day(d):
            return {"date": d["date"].isoformat(), "day": d["date"].day, "in_month": d["in_month"], "is_today": d["is_today"], "is_weekend": d["is_weekend"],
                    "holiday": d["holiday"], "off_count": d["off_count"], "entries": d["entries"]}
        return Response({
            "label": cal["first"].strftime("%B %Y"), "prev": f"{py:04d}-{pm:02d}", "next": f"{ny:04d}-{nm:02d}", "is_current": (year, month) == (today.year, today.month),
            "me_id": request.user.pk, "show_types": show_types, "team": cal["team"],
            "weeks": [[day(d) for d in w] for w in cal["weeks"]], "agenda": [day(d) for d in cal["agenda"]],
        })


class QueueAPIView(CompanyAPIView):
    def get(self, request):
        _approver(request)
        status = request.query_params.get("status", LeaveRequest.Status.PENDING)
        if status not in dict(LeaveRequest.Status.choices):
            status = LeaveRequest.Status.PENDING
        rows = list(LeaveRequest.objects.filter(company=request.company, status=status).select_related("user", "policy", "decided_by").order_by("start_date"))
        counts = {r["status"]: r["n"] for r in LeaveRequest.objects.filter(company=request.company).values("status").annotate(n=Count("id"))}
        items = []
        for leave in rows:
            extra = {"person": {"id": leave.user_id, "name": _name(leave.user), "username": leave.user.username}}
            if status == LeaveRequest.Status.PENDING:
                preview = service.decision_preview(request.company, leave)
                clash = service.clash_for(request.company, leave.user, leave.start_date, leave.end_date, exclude_pk=leave.pk)
                extra.update({
                    "auto_paid": _d1(preview["paid"]), "auto_unpaid": _d1(preview["unpaid"]), "auto_paid_label": preview["paid_label"],
                    "auto_unpaid_label": preview["unpaid_label"], "reasons": preview["reasons"], "clash_people": clash["people"], "clash_text": service.clash_sentence(clash),
                })
            items.append(request_json(leave, **extra))
        return Response({
            "status": status, "tabs": [{"value": v, "label": l, "count": counts.get(v, 0)} for v, l in LeaveRequest.Status.choices], "items": items,
        })


class DecisionAPIView(CompanyAPIView):
    def post(self, request, pk, action):
        _approver(request)
        if action not in ("approve", "reject"):
            raise PermissionDenied("Unknown action.")
        leave = get_object_or_404(LeaveRequest.objects.select_related("user", "policy"), pk=pk, company=request.company)
        message, problem = actions.decide(request.company, request.user, leave, action, request.data)
        if message is None:
            detail = problem if isinstance(problem, str) else " ".join(problem)
            return Response({"detail": detail}, status=400)
        return Response({"message": message})


def policy_json(p):
    return {
        "id": p.pk, "name": p.name, "max_days_per_year": _num(p.max_days_per_year), "max_consecutive_days": _num(p.max_consecutive_days),
        "is_paid": p.is_paid, "color": p.color, "icon": p.icon, "annual_label": p.annual_limit_label, "spell_label": p.consecutive_limit_label,
    }


class PolicyListAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        return Response({
            "policies": [policy_json(p) for p in service.policies_for(request.company)],
            "colors": [list(c) for c in LeavePolicy.COLOR_TOKENS], "icons": [[v, l] for v, l in ICON_CHOICES],
        })

    def post(self, request):
        _admin(request)
        policy, form = actions.save_policy(request.company, request.user, request.data)
        if policy is None:
            return Response(form_errors(form), status=400)
        return Response({"policy": policy_json(policy), "message": f"{policy.name} leave type added."}, status=201)


class PolicyAPIView(CompanyAPIView):
    def patch(self, request, pk):
        _admin(request)
        policy = get_object_or_404(LeavePolicy, pk=pk, company=request.company)
        saved, form = actions.save_policy(request.company, request.user, request.data, policy)
        if saved is None:
            return Response(form_errors(form), status=400)
        return Response({"policy": policy_json(saved), "message": f"{saved.name} leave policy updated."})

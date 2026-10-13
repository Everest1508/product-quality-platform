import datetime
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Membership
from apps.attendance.service import _company_members
from apps.payroll import actions, service
from apps.payroll.models import Holiday, Payslip, PayrollProfile, PayrollRun
from apps.uiapi.tickets import form_errors
from apps.uiapi.views import CompanyAPIView

ZERO = Decimal("0.00")


def _admin(request):
    if request.company_role not in ("owner", "admin"):
        raise PermissionDenied("Only company admins can perform this action.")


def _name(u):
    return u.get_full_name() or u.username


def _person(u):
    return {"id": u.pk, "name": _name(u), "username": u.username, "initial": _name(u)[:1].upper()}


def _cycle(request, source):
    """The cycle asked for by `anchor` (any date in it), defaulting to the one running today."""
    try:
        anchor = datetime.date.fromisoformat(source.get("anchor") or source.get("cycle") or "")
    except (TypeError, ValueError):
        anchor = timezone.localdate()
    if not 1900 <= anchor.year <= 2200:
        anchor = timezone.localdate()
    return service.cycle_bounds(anchor)


def _d(v):
    return None if v is None else str(v)


def run_json(run, slips=None):
    slips = list(run.payslips.all()) if slips is None else slips
    return {
        "id": run.pk, "label": run.label, "start": run.period_start.isoformat(), "end": run.period_end.isoformat(), "working_days": run.working_days,
        "is_locked": run.is_locked, "payslips": len(slips), "total_deduction": str(run.total_deduction), "total_gross": str(run.total_gross),
    }


def slip_json(p, full=True):
    b = p.breakdown or {}
    return {
        "id": p.pk, "person": _person(p.user), "currency": p.currency, "daily_rate": str(p.daily_rate), "working_days": p.working_days,
        "paid_leave_days": str(p.paid_leave_days), "unpaid_leave_days": str(p.unpaid_leave_days), "payable_days": str(p.payable_days),
        "deduction": str(p.deduction), "gross": str(p.gross), "late_half_days": str(p.late_half_days), "late_penalty": str(p.late_penalty),
        "run": {"id": p.run_id, "label": p.run.label, "start": p.run.period_start.isoformat(), "end": p.run.period_end.isoformat(), "is_locked": p.run.is_locked},
        "monthly_salary": b.get("monthly_salary"), "divisor_days": b.get("working_days"), "breakdown_daily_rate": b.get("daily_rate"),
        "late_events": b.get("late_events", []) if full else [],
    }


def row_json(r):
    return {
        "person": _person(r["user"]), "currency": r["currency"], "daily_rate": str(r["daily_rate"]), "monthly_salary": r["breakdown"].get("monthly_salary"),
        "paid_leave_days": str(r["paid_leave_days"]), "unpaid_leave_days": str(r["unpaid_leave_days"]), "payable_days": str(r["payable_days"]),
        "deduction": str(r["deduction"]), "gross": str(r["gross"]),
    }


class RunListAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        runs = list(PayrollRun.objects.filter(company=request.company).prefetch_related("payslips"))
        start, end = service.cycle_bounds(timezone.localdate())
        return Response({
            "runs": [run_json(r) for r in runs], "current": {"start": start.isoformat(), "end": end.isoformat()},
            "has_current_run": any(r.period_start == start and r.period_end == end for r in runs),
        })


class PreviewAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        start, end = _cycle(request, request.query_params)
        working, rows = service.preview(request.company, start, end)
        return Response({
            "start": start.isoformat(), "end": end.isoformat(), "working_days": working, "rows": [row_json(r) for r in rows],
            "total_gross": str(sum((r["gross"] for r in rows), ZERO)), "total_deduction": str(sum((r["deduction"] for r in rows), ZERO)),
        })

    def post(self, request):
        _admin(request)
        start, end = _cycle(request, request.data)
        run, message = actions.generate(request.company, request.user, start, end)
        return Response({"run_id": run.pk, "message": message})


class RunAPIView(CompanyAPIView):
    def get(self, request, pk):
        _admin(request)
        run = get_object_or_404(PayrollRun, pk=pk, company=request.company)
        slips = list(run.payslips.select_related("user", "run").order_by("user__username"))
        return Response({
            **run_json(run, slips), "slips": [slip_json(p, full=False) for p in slips],
            "total_payable": str(sum((p.payable_days for p in slips), ZERO)),
        })


class RunLockAPIView(CompanyAPIView):
    def post(self, request, pk):
        _admin(request)
        run = get_object_or_404(PayrollRun, pk=pk, company=request.company)
        message = actions.toggle_lock(request.company, request.user, run)
        return Response({"is_locked": run.is_locked, "message": message})


class PayslipAPIView(CompanyAPIView):
    def get(self, request, pk):
        _admin(request)
        return Response(slip_json(get_object_or_404(Payslip.objects.select_related("run", "user"), pk=pk, company=request.company)))


class MyPayslipsAPIView(CompanyAPIView):
    def get(self, request):
        slips = Payslip.objects.filter(company=request.company, user=request.user).select_related("run", "user").order_by("-run__period_start")
        latest = PayrollProfile.objects.filter(company=request.company, user=request.user).order_by("-effective_from").first()
        start, end = service.cycle_bounds(timezone.localdate())
        return Response({
            "payslips": [slip_json(p, full=False) for p in slips], "on_payroll": bool(latest and latest.is_on_payroll),
            "cycle": {"start": start.isoformat(), "end": end.isoformat()}, "is_admin": request.company_role in ("owner", "admin"),
        })


class MyPayslipAPIView(CompanyAPIView):
    """Someone else's slip is a 404, not a 403: a refusal would confirm the id exists."""

    def get(self, request, pk):
        return Response(slip_json(get_object_or_404(Payslip.objects.select_related("run", "user"), pk=pk, company=request.company, user=request.user)))


def holiday_json(h):
    return {"id": h.pk, "date": h.date.isoformat(), "label": h.date.strftime("%a, %-d %b %Y"), "name": h.name}


class HolidayListAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        return Response({"holidays": [holiday_json(h) for h in Holiday.objects.filter(company=request.company)]})

    def post(self, request):
        _admin(request)
        holiday, form = actions.add_holiday(request.company, request.user, request.data)
        if holiday is None:
            return Response(form_errors(form), status=400)
        return Response({"holiday": holiday_json(holiday), "message": f"{holiday.name} added."}, status=201)


class HolidayAPIView(CompanyAPIView):
    def delete(self, request, pk):
        _admin(request)
        holiday = get_object_or_404(Holiday, pk=pk, company=request.company)
        return Response({"message": actions.remove_holiday(request.company, request.user, holiday)})


def _profile_rows(company):
    profiles = {}
    for p in PayrollProfile.objects.filter(company=company).select_related("user"):
        profiles.setdefault(p.user_id, []).append(p)
    memberships = {m.user_id: m for m in Membership.objects.filter(company=company)}
    start, end = service.cycle_bounds(timezone.localdate())
    working, preview_rows = service.preview(company, start, end)
    estimates = {r["user"].pk: r for r in preview_rows}
    rows = []
    for member in _company_members(company):
        history = sorted(profiles.get(member.pk, []), key=lambda p: p.effective_from, reverse=True)
        latest = history[0] if history else None
        est = estimates.get(member.pk)
        rows.append({
            "membership_id": memberships[member.pk].pk if member.pk in memberships else None, "role": memberships[member.pk].role if member.pk in memberships else "",
            "person": _person(member), "is_on_payroll": bool(latest and latest.is_on_payroll), "has_profile": latest is not None,
            "monthly_salary": _d(latest.monthly_salary) if latest else None, "daily_rate": _d(latest.daily_rate) if latest else None,
            "currency": latest.currency if latest else "INR", "effective_from": (latest.effective_from if latest else timezone.localdate()).isoformat(),
            "rates": len(history), "since": latest.effective_from.strftime("%-d %b %Y") if latest else "",
            "estimate": {"gross": str(est["gross"]), "payable_days": str(est["payable_days"].normalize()), "unpaid_leave_days": str(est["unpaid_leave_days"])} if est else None,
        })
    on = sum(1 for r in rows if r["is_on_payroll"])
    return {
        "rows": rows, "on_payroll": on, "off_payroll": len(rows) - on, "working_days": working,
        "cycle": {"start": start.isoformat(), "end": end.isoformat(), "label": f"{start.strftime('%-d %b')}–{end.strftime('%-d %b')}"},
        "cycle_gross": str(sum((r["gross"] for r in preview_rows), ZERO)),
    }


class ProfileListAPIView(CompanyAPIView):
    def get(self, request):
        _admin(request)
        return Response(_profile_rows(request.company))

    def post(self, request):
        _admin(request)
        pk = str(request.data.get("membership", ""))
        membership = get_object_or_404(Membership, pk=int(pk) if pk.isdecimal() else 0, company=request.company)
        message, form = actions.save_profile(request.company, request.user, membership, request.data)
        if message is None:
            return Response(form_errors(form), status=400)
        return Response({**_profile_rows(request.company), "message": message})

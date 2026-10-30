from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dates import WEEKDAYS, WEEKDAYS_ABBR
from django.views import View

from apps.attendance.service import shift_for
from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.payroll import service
from apps.payroll.forms import HolidayForm, PayrollProfileForm
from apps.payroll.models import Holiday, Payslip, PayrollProfile, PayrollRun


class PayrollPageMixin:
    """Section shell shared by every /payroll/ page.

    `payroll/base.html` renders the breadcrumbs and the Runs/Salaries/Holidays
    tabs from `pay_section`. The six pages used to each hand-roll their own
    navigation and header markup, which is how they drifted apart; they now
    supply content and a section name only.
    """

    pay_section = None

    def page(self, request, context=None, **extra):
        merged = dict(context or {})
        merged.update(extra)
        merged.setdefault("pay_section", self.pay_section)
        return render(request, self.template_name, merged)


def _requested_cycle(request):
    """The cycle asked for, from `month` (2026-10 is 27 Sep to 26 Oct) in the query or the form.

    Read from the query string and the posted form alike, so "Create payslips"
    makes exactly the cycle that was on screen. With nothing asked for it is the
    newest finished cycle, the one that is ready to pay. An old `anchor` or
    `cycle` date still works.
    """
    today = timezone.localdate()
    data = request.POST if request.method == "POST" else request.GET
    picked = service.cycle_from_key(data.get("month", ""))
    if picked:
        return picked
    for name in ("anchor", "cycle"):
        try:
            return service.cycle_bounds(date.fromisoformat(data.get(name, "")))
        except ValueError:
            continue
    return service.last_finished_cycle(today)


def _log(request, event, title, target, description="", metadata=None,
         content_type="payroll_run"):
    return log_activity(
        request.company,
        event,
        title,
        description=description,
        actor=request.user,
        target_content_type=content_type,
        target_object_id=target.pk if target is not None else None,
        metadata=metadata,
    )


class PayrollRunListView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    """Past cycles and the cycle currently running."""

    template_name = "payroll/run_list.html"
    pay_section = "runs"

    def get(self, request):
        runs = PayrollRun.objects.filter(company=request.company).prefetch_related(
            "payslips"
        )
        current_start, current_end = service.cycle_bounds(timezone.localdate())
        return self.page(
            request,
            {
                "runs": runs,
                "current_start": current_start,
                "current_end": current_end,
                "has_current_run": runs.filter(
                    period_start=current_start, period_end=current_end
                ).exists(),
            },
        )


class PayrollPreviewView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    """What a cycle would pay, before it is generated.

    Read-only by design: nobody should be looking at an authoritative number
    that has not been snapshotted into a run yet.
    """

    template_name = "payroll/preview.html"
    pay_section = "runs"

    def get(self, request):
        start, end = _requested_cycle(request)
        working, rows = service.preview(request.company, start, end)
        return self.page(
            request,
            {
                "period_start": start,
                "period_end": end,
                "working_days": working,
                "rows": rows,
                "cycle_options": service.cycle_options(request.company, timezone.localdate()),
                "cycle_key": service.cycle_key(end),
                "existing_run": PayrollRun.objects.filter(
                    company=request.company, period_start=start, period_end=end
                ).first(),
                "total_repaid": sum((r["reimbursement"] for r in rows), Decimal("0.00")),
                "total_gross": sum((r["gross"] for r in rows), Decimal("0.00")),
                "total_deduction": sum(
                    (r["deduction"] for r in rows), Decimal("0.00")
                ),
            },
        )

    def post(self, request):
        start, end = _requested_cycle(request)
        run, created = service.generate_run(
            request.company, start, end, created_by=request.user
        )
        if created:
            messages.success(request, f"Payroll generated for {run.label}.")
        else:
            messages.info(request, f"{run.label} is locked and was left unchanged.")
        return redirect("payroll:run_detail", pk=run.pk)


def _calc_lines(run, p):
    """The arithmetic behind one stored payslip, from its own snapshot, for the popup."""
    b = p.breakdown or {}
    cycle = b.get("cycle_days")
    cash = p.late_penalty or Decimal("0.00")
    back = p.reimbursement or Decimal("0.00")
    earned = p.gross + cash - back
    paid_days = b.get("paid_days_of", "").split(" of ")[0] or cycle or p.working_days
    return {
        # Whatever was taken off, so the steps always add up to the stored payable days.
        "late_days": Decimal(paid_days) - p.unpaid_leave_days - p.payable_days,
        "late_count": p.late_half_days,
        "paid_days": paid_days,
        "monthly": b.get("monthly_salary"),
        "cycle_days": cycle,
        "joined_on": b.get("joined_on"),
        "earned": earned,
        "cash": cash,
        "back": back,
        "events": b.get("late_events") or [],
        "uncapped": b.get("late_penalty_uncapped"),
    }


class PayrollRunDetailView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    template_name = "payroll/run_detail.html"
    pay_section = "runs"

    def get(self, request, pk):
        run = get_object_or_404(PayrollRun, pk=pk, company=request.company)
        slips = run.payslips.select_related("user").order_by("user__username")
        if request.GET.get("export") == "csv":
            from apps.core.csvx import csv_response

            return csv_response(
                f"payroll-{run.period_start}-to-{run.period_end}.csv",
                ["Employee", "Currency", "Monthly salary", "Working days", "Paid leave days", "Unpaid leave days", "Late half days", "Late penalty", "Payable days", "Deduction", "Expenses repaid", "Gross"],
                [[(p.user.get_full_name() or p.user.username), p.currency, (p.breakdown or {}).get("monthly_salary", ""), p.working_days, p.paid_leave_days, p.unpaid_leave_days, p.late_half_days, p.late_penalty, p.payable_days, p.deduction, p.reimbursement, p.gross] for p in slips],
            )
        slips = list(slips)
        fresh = {}
        if not run.is_locked:
            _, rows = service.preview(request.company, run.period_start, run.period_end)
            fresh = {r["user"].pk: r for r in rows}
        stale = 0
        for p in slips:
            p.calc = _calc_lines(run, p)
            row = fresh.get(p.user_id)
            # An open run is a snapshot; flag it when today's rules give other numbers.
            p.stale = bool(fresh) and (
                row is None
                or (row["daily_rate"], row["payable_days"], row["deduction"], row["gross"])
                != (p.daily_rate, p.payable_days, p.deduction, p.gross)
            )
            p.now = row
            stale += p.stale
        return self.page(
            request,
            {
                "run": run,
                "payslips": slips,
                "stale_count": stale,
                "total_gross": run.total_gross,
                "total_deduction": run.total_deduction,
                "total_payable": sum(
                    (p.payable_days for p in slips), Decimal("0.00")
                ),
            },
        )


class PayrollRunLockView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    """Lock a cycle so it stops being recalculated."""

    def post(self, request, pk):
        run = get_object_or_404(PayrollRun, pk=pk, company=request.company)
        run.is_locked = not run.is_locked
        run.save(update_fields=["is_locked"])
        state = "locked" if run.is_locked else "unlocked"
        _log(
            request,
            f"payroll_run_{state}",
            f"Payroll run {state}: {run.label}",
            run,
            metadata={"is_locked": run.is_locked},
        )
        messages.success(
            request,
            f"{run.label} {'locked' if run.is_locked else 'unlocked'}.",
        )
        return redirect("payroll:run_detail", pk=run.pk)


class PayslipDetailView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    template_name = "payroll/payslip.html"
    pay_section = "runs"

    def get(self, request, pk):
        payslip = get_object_or_404(
            Payslip.objects.select_related("run", "user", "profile"),
            pk=pk,
            company=request.company,
        )
        return self.page(request, payslip=payslip, c=_calc_lines(payslip.run, payslip))


class PayslipDeleteView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    """Remove one payslip from an open run, for one generated by mistake.

    A locked run is refused: its slips are the record of what was issued. Re-previewing and
    generating the cycle creates the slip again if the person is still on payroll, so to
    keep someone off for good, switch them off in Salaries first.
    """

    def post(self, request, pk):
        slip = get_object_or_404(Payslip.objects.select_related("run", "user"), pk=pk, company=request.company)
        run = slip.run
        who = slip.user.get_full_name() or slip.user.username
        if run.is_locked:
            messages.error(request, f"{run.label} is locked. Unlock it before deleting a payslip.")
            return redirect("payroll:payslip", pk=slip.pk)
        slip.delete()
        _log(request, "payroll_payslip_deleted", f"Payslip deleted: {who}, {run.label}", run,
             metadata={"user_id": slip.user_id})
        messages.success(request, f"Deleted {who}'s payslip for {run.label}.")
        return redirect("payroll:run_detail", pk=run.pk)


class MyPayslipListView(PayrollPageMixin, CompanyMemberRequiredMixin, View):
    """A person's own payslips, newest cycle first.

    Open to every company member, not just admins: an employee's pay is their
    own business, and hiding it means someone can have unpaid leave approved and
    their pay cut with no way to check what they were paid. The queryset is
    pinned to `request.user` and there is no user id in the URL, so there is
    nothing to edit to reach a colleague's slip.
    """

    template_name = "payroll/my_payslips.html"
    pay_section = "mine"

    def get(self, request):
        payslips = (
            Payslip.objects.filter(company=request.company, user=request.user)
            .select_related("run")
            .order_by("-run__period_start")
        )
        # "Are you on payroll at all?" comes from the latest profile, not from
        # whether a payslip happens to exist yet — someone switched on
        # mid-cycle has no payslip until the run is generated.
        latest = (
            PayrollProfile.objects.filter(company=request.company, user=request.user)
            .order_by("-effective_from")
            .first()
        )
        return self.page(
            request,
            payslips=payslips,
            on_payroll=bool(latest and latest.is_on_payroll),
            cycle_start=service.cycle_bounds(timezone.localdate())[0],
            cycle_end=service.cycle_bounds(timezone.localdate())[1],
        )


class MyPayslipDetailView(PayrollPageMixin, CompanyMemberRequiredMixin, View):
    """One of the viewer's own payslips.

    Scoped to `user=request.user` in the query, not just `company`, so another
    person's slip is a 404 rather than a permission error that confirms it
    exists. 404 not 403 on purpose: a 403 would leak the pk's existence.
    """

    template_name = "payroll/my_payslip.html"
    pay_section = "mine"

    def get(self, request, pk):
        payslip = get_object_or_404(
            Payslip.objects.select_related("run", "profile"),
            pk=pk,
            company=request.company,
            user=request.user,
        )
        return self.page(request, payslip=payslip, c=_calc_lines(payslip.run, payslip))


class HolidayListView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    template_name = "payroll/holidays.html"
    pay_section = "holidays"

    def get(self, request):
        return self.page(
            request,
            {
                "holidays": Holiday.objects.filter(company=request.company),
                "form": HolidayForm(company=request.company),
                "weekly_off": shift_for(request.company).off_weekdays,
                "weekdays": [(n, str(WEEKDAYS_ABBR[n]), str(WEEKDAYS[n])) for n in WEEKDAYS],
            },
        )

    def post(self, request):
        form = HolidayForm(request.POST, company=request.company)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.company = request.company
            holiday.save()
            _log(
                request,
                "holiday_added",
                f"Holiday added: {holiday.name}",
                holiday,
                description=str(holiday.date),
                content_type="holiday",
            )
            messages.success(request, f"{holiday.name} added.")
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
        return redirect("payroll:holidays")


class HolidayDeleteView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        holiday = get_object_or_404(Holiday, pk=pk, company=request.company)
        name = holiday.name
        removed_date = holiday.date
        pk = holiday.pk
        holiday.delete()
        _log(
            request,
            "holiday_removed",
            f"Holiday removed: {name}",
            None,
            description=str(removed_date),
            content_type="holiday",
            metadata={"holiday_id": pk},
        )
        messages.success(request, f"{name} removed.")
        return redirect("payroll:holidays")


class PayrollProfileListView(PayrollPageMixin, CompanyAdminRequiredMixin, View):
    """Set a monthly salary and decide who is on payroll."""

    template_name = "payroll/profiles.html"
    pay_section = "salaries"

    def get(self, request):
        from apps.accounts.models import Membership
        from apps.attendance.service import _company_members

        profiles = {}
        for profile in PayrollProfile.objects.filter(
            company=request.company
        ).select_related("user"):
            profiles.setdefault(profile.user_id, []).append(profile)

        # The membership for *this* company, not the user's first one ever:
        # the form posts it back and the view 404s on a foreign pk.
        memberships = {
            m.user_id: m
            for m in Membership.objects.filter(company=request.company)
        }

        # What the current cycle would pay, so the page can show a number
        # instead of asking someone to trust a rate. service.preview owns the
        # maths; the day counts must not be re-derived here.
        cycle_start, cycle_end = service.cycle_bounds(timezone.localdate())
        working_days, preview_rows = service.preview(
            request.company, cycle_start, cycle_end
        )
        estimates = {row["user"].pk: row for row in preview_rows}
        cycle_day_count = service.cycle_days(cycle_start, cycle_end)

        rows = []
        for member in _company_members(request.company):
            history = sorted(
                profiles.get(member.pk, []), key=lambda p: p.effective_from, reverse=True
            )
            form = PayrollProfileForm(
                user=member, company=request.company,
                initial=self._initial(member, history),
            )
            # One form per person, so the visible column headers label nobody in
            # particular. Name each control for the person it belongs to.
            who = member.get_full_name() or member.username
            form["is_on_payroll"].field.widget.attrs["aria-label"] = f"{who} on payroll"
            form["monthly_salary"].field.widget.attrs["aria-label"] = (
                f"{who} monthly salary"
            )
            form["currency"].field.widget.attrs["aria-label"] = f"{who} currency"
            form["currency"].field.widget.attrs["class"] = "form-input aux"
            # One form per person means one id per person; the default
            # id_currency would repeat down the page. is_on_payroll and
            # effective_from need the same treatment or their ids repeat too,
            # which makes the column-header labels ambiguous.
            form["currency"].field.widget.attrs["id"] = f"id_currency_{member.pk}"
            form["is_on_payroll"].field.widget.attrs["id"] = f"id_is_on_payroll_{member.pk}"
            form["effective_from"].field.widget.attrs["id"] = f"id_effective_from_{member.pk}"
            form["effective_from"].field.widget.attrs["aria-label"] = (
                f"{who} rate effective from"
            )
            rows.append(
                {
                    "user": member,
                    "membership": memberships.get(member.pk),
                    "profile": history[0] if history else None,
                    "history": history,
                    "estimate": estimates.get(member.pk),
                    "form": form,
                }
            )

        on_payroll = [r for r in rows if r["profile"] and r["profile"].is_on_payroll]
        context = {
            "rows": rows,
            "on_payroll_count": len(on_payroll),
            "off_payroll_count": len(rows) - len(on_payroll),
            "never_set_count": sum(1 for r in rows if r["profile"] is None),
            # The cycle the estimate column is priced against.
            "cycle_start": cycle_start,
            "cycle_end": cycle_end,
            "working_days": working_days,
            "cycle_days": cycle_day_count,
            "cycle_gross": sum(
                (r["estimate"]["gross"] for r in rows if r["estimate"]), Decimal("0.00")
            ),
        }
        return self.page(request, **context)

    @staticmethod
    def _initial(member, history):
        if not history:
            return {
                "currency": "INR",
                "effective_from": timezone.localdate(),
                "is_on_payroll": False,
            }
        latest = history[0]
        return {
            # A profile saved before monthly salary existed has none, so the
            # screen falls back to showing its daily rate.
            "monthly_salary": latest.monthly_salary,
            "currency": latest.currency,
            # Prefilled with the date the current rate already starts, so a
            # corrected rate edits that row instead of quietly opening a new
            # one from today. A deliberate date change is how you record a raise.
            "effective_from": latest.effective_from,
            "is_on_payroll": latest.is_on_payroll,
        }

    def post(self, request):
        from apps.accounts.models import Membership

        membership = get_object_or_404(
            Membership, pk=request.POST.get("membership"), company=request.company
        )
        form = PayrollProfileForm(
            request.POST, user=membership.user, company=request.company
        )
        if not form.is_valid():
            for error in form.errors.values():
                messages.error(request, error[0])
            return redirect("payroll:profiles")

        effective_from = form.cleaned_data["effective_from"]
        saved = PayrollProfile.objects.filter(
            company=request.company,
            user=membership.user,
            effective_from=effective_from,
        ).first()
        if saved:
            # Same start date: this edits that rate instead of adding one.
            for field, value in form.cleaned_data.items():
                setattr(saved, field, value)
            saved.save()
            action = "updated"
        else:
            saved = form.save(commit=False)
            saved.company = request.company
            saved.user = membership.user
            saved.save()
            action = "set"

        _log(
            request,
            "payroll_profile_saved",
            f"Payroll {action} for {membership.user.username}",
            saved,
            description=(
                f"{form.cleaned_data['monthly_salary']} per month"
                if form.cleaned_data.get("monthly_salary")
                else f"{form.cleaned_data['daily_rate']} per day"
            ),
            content_type="payroll_profile",
            metadata={"currency": form.cleaned_data["currency"]},
        )
        messages.success(
            request,
            f"Payroll {action} for {membership.user.username}.",
        )
        return redirect("payroll:profiles")

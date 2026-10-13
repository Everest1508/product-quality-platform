"""Payroll writes shared by the JSON API: each one logs the activity the summary reports are built from."""
from apps.dashboards.service import log_activity
from apps.payroll import service
from apps.payroll.forms import HolidayForm, PayrollProfileForm
from apps.payroll.models import Holiday, PayrollProfile


def _log(company, actor, event, title, target, description="", metadata=None, content_type="payroll_run"):
    return log_activity(
        company, event, title, description=description, actor=actor, target_content_type=content_type,
        target_object_id=target.pk if target is not None else None, metadata=metadata,
    )


def generate(company, actor, start, end):
    """Snapshot a cycle. Returns (run, message)."""
    run, created = service.generate_run(company, start, end, created_by=actor)
    if created:
        return run, f"Payroll generated for {run.label}."
    return run, f"{run.label} is locked and was left unchanged."


def toggle_lock(company, actor, run):
    run.is_locked = not run.is_locked
    run.save(update_fields=["is_locked"])
    state = "locked" if run.is_locked else "unlocked"
    _log(company, actor, f"payroll_run_{state}", f"Payroll run {state}: {run.label}", run, metadata={"is_locked": run.is_locked})
    return f"{run.label} {state}."


def add_holiday(company, actor, data):
    """Returns (holiday, form); holiday is None when invalid."""
    form = HolidayForm(data, company=company)
    if not form.is_valid():
        return None, form
    holiday = form.save(commit=False)
    holiday.company = company
    holiday.save()
    _log(company, actor, "holiday_added", f"Holiday added: {holiday.name}", holiday, description=str(holiday.date), content_type="holiday")
    return holiday, form


def remove_holiday(company, actor, holiday):
    name, removed_date, pk = holiday.name, holiday.date, holiday.pk
    holiday.delete()
    _log(company, actor, "holiday_removed", f"Holiday removed: {name}", None, description=str(removed_date), content_type="holiday", metadata={"holiday_id": pk})
    return f"{name} removed."


def save_profile(company, actor, membership, data):
    """Set or edit a rate. The same start date edits that rate; a new date opens a new one. Returns (message, form)."""
    form = PayrollProfileForm(data, user=membership.user, company=company)
    if not form.is_valid():
        return None, form
    c = form.cleaned_data
    saved = PayrollProfile.objects.filter(company=company, user=membership.user, effective_from=c["effective_from"]).first()
    if saved:
        for field, value in c.items():
            setattr(saved, field, value)
        saved.save()
        action = "updated"
    else:
        saved = form.save(commit=False)
        saved.company, saved.user = company, membership.user
        saved.save()
        action = "set"
    _log(
        company, actor, "payroll_profile_saved", f"Payroll {action} for {membership.user.username}", saved,
        description=f"{c['monthly_salary']} per month" if c.get("monthly_salary") else f"{c['daily_rate']} per day",
        content_type="payroll_profile", metadata={"currency": c["currency"]},
    )
    return f"Payroll {action} for {membership.user.username}.", form

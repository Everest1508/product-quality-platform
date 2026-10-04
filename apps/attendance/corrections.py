"""Attendance corrections: ask, approve, reject, cancel.

The rules live here, not in the views, so the form, the queue and the tests all
go through the same checks.

* An employee asks for new times for one day in the last 60 days, with a reason.
* Only the times they give are changed. A day with no punch needs a check-in.
* One open request per person per day.
* An owner or admin decides. Nobody decides their own request unless they are
  the only owner or admin, so a lone owner is not locked out of fixing their own day.
* Approval applies the times with the same validation as an admin edit, marks
  the record as edited, logs it, and tells the employee.
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membership
from apps.attendance import service
from apps.attendance.models import AttendanceCorrection, AttendanceRecord
from apps.dashboards.service import log_activity
from apps.notifications import service as notifications
from apps.notifications.models import Notification

MAX_AGE_DAYS = 60
ADMIN_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


class CorrectionError(Exception):
    """A problem the person can fix. The message is shown to them as is."""


def build_datetime(day, clock, next_day=False):
    """`clock` ('HH:MM' or a time) on `day` as an aware datetime, or None if empty."""
    if clock in (None, ""):
        return None
    if isinstance(clock, str):
        try:
            clock = datetime.strptime(clock.strip(), "%H:%M").time()
        except ValueError:
            raise CorrectionError("Times need the form HH:MM.")
    moment = datetime.combine(day + timedelta(days=1 if next_day else 0), clock)
    return timezone.make_aware(moment, timezone.get_current_timezone())


def admins(company):
    return [
        m.user
        for m in Membership.objects.filter(company=company, role__in=ADMIN_ROLES).select_related("user")
    ]


def company_of(correction):
    return correction.company


def can_decide(approver, correction):
    """Owners and admins decide. Your own request needs someone else, unless you
    are the only owner or admin."""
    membership = Membership.objects.filter(user=approver, company=correction.company).first()
    if membership is None or membership.role not in ADMIN_ROLES:
        return False
    if approver.pk != correction.user_id:
        return True
    others = Membership.objects.filter(company=correction.company, role__in=ADMIN_ROLES).exclude(user=approver)
    return not others.exists()


def request_correction(user, company, day, check_in, check_out, reason):
    reason = (reason or "").strip()
    today = timezone.localdate()
    if day > today:
        raise CorrectionError("You can only correct a day that has already started.")
    if day < today - timedelta(days=MAX_AGE_DAYS):
        raise CorrectionError(f"Corrections go back {MAX_AGE_DAYS} days. Ask an admin to edit older days.")
    if not reason:
        raise CorrectionError("Say why the times are wrong.")
    if len(reason) > 500:
        raise CorrectionError("Keep the reason under 500 characters.")
    if check_in is None and check_out is None:
        raise CorrectionError("Enter a check-in time, a check-out time, or both.")

    record = AttendanceRecord.objects.filter(company=company, user=user, date=day).first()
    if (record is None or record.check_in is None) and check_in is None:
        raise CorrectionError("That day has no check-in, so a check-in time is needed.")

    final_in = check_in or (record.check_in if record else None)
    final_out = check_out or (record.check_out if record else None)
    problem = service.punch_problem(day, check_in, check_out)
    if problem:
        raise CorrectionError(problem)
    if final_in and final_out and final_out < final_in:
        raise CorrectionError("Check-out cannot be before check-in.")

    if AttendanceCorrection.objects.filter(
        company=company, user=user, date=day, status=AttendanceCorrection.Status.PENDING
    ).exists():
        raise CorrectionError("You already have a request waiting for that day.")

    correction = AttendanceCorrection.objects.create(
        company=company,
        user=user,
        date=day,
        record=record,
        requested_check_in=check_in,
        requested_check_out=check_out,
        original_check_in=record.check_in if record else None,
        original_check_out=record.check_out if record else None,
        reason=reason,
    )
    who = user.get_full_name() or user.username
    notifications.notify_many(
        admins(company),
        company=company,
        kind=Notification.Kind.CORRECTION_REQUEST,
        title=f"{who} asked to correct {day:%b %d}",
        body=reason[:140],
        url="/attendance/corrections/",
        actor=user,
    )
    log_activity(
        company,
        "attendance_correction_requested",
        f"{who} asked to correct attendance on {day:%b %d, %Y}",
        description=reason[:200],
        actor=user,
        target_content_type="attendance_correction",
        target_object_id=correction.pk,
        metadata={"date": day.isoformat()},
    )
    return correction


@transaction.atomic
def decide(correction_id, approver, approve, note=""):
    """Approve or reject. Returns the correction. Raises CorrectionError."""
    correction = AttendanceCorrection.objects.select_for_update().select_related("user").get(pk=correction_id)
    if not correction.is_pending:
        raise CorrectionError("That request has already been dealt with.")
    if not can_decide(approver, correction):
        membership = Membership.objects.filter(user=approver, company=company_of(correction)).first()
        if membership is None or membership.role not in ADMIN_ROLES:
            raise CorrectionError("Only owners and admins can decide corrections.")
        raise CorrectionError("Another owner or admin has to decide your own request.")

    company, user, day = correction.company, correction.user, correction.date
    note = (note or "").strip()[:255]

    if approve:
        record = AttendanceRecord.objects.filter(company=company, user=user, date=day).first()
        final_in = correction.requested_check_in or (record.check_in if record else None)
        final_out = correction.requested_check_out or (record.check_out if record else None)
        # Checked again now: the record may have changed since the request.
        problem = service.punch_problem(day, correction.requested_check_in, correction.requested_check_out)
        if problem:
            raise CorrectionError(problem)
        if final_in is None:
            raise CorrectionError("That day still has no check-in.")
        if final_out and final_out < final_in:
            raise CorrectionError("Check-out would be before check-in. Reject it, or ask for new times.")
        if record is None:
            record = AttendanceRecord(company=company, user=user, date=day)
        record.check_in, record.check_out = final_in, final_out
        record.is_edited = True
        if not record.notes:
            record.notes = f"Corrected: {correction.reason}"[:255]
        record.save()
        correction.record = record
        correction.status = AttendanceCorrection.Status.APPROVED
    else:
        correction.status = AttendanceCorrection.Status.REJECTED

    correction.decided_by = approver
    correction.decided_at = timezone.now()
    correction.decision_note = note
    correction.save()

    verdict = "approved" if approve else "rejected"
    boss = approver.get_full_name() or approver.username
    notifications.notify(
        user=user,
        company=company,
        kind=Notification.Kind.CORRECTION_DECISION,
        title=f"Your correction for {day:%b %d} was {verdict}",
        body=(note or f"Decided by {boss}")[:140],
        url=f"/attendance/?month={day:%Y-%m}",
        actor=approver,
    )
    log_activity(
        company,
        f"attendance_correction_{verdict}",
        f"Attendance correction for {user.get_full_name() or user.username} on {day:%b %d, %Y} {verdict}",
        description=note or correction.reason[:200],
        actor=approver,
        target_content_type="attendance_correction",
        target_object_id=correction.pk,
        metadata={"date": day.isoformat(), "user_id": user.pk},
    )
    return correction


def cancel(correction_id, user):
    with transaction.atomic():
        correction = AttendanceCorrection.objects.select_for_update().get(pk=correction_id)
        if correction.user_id != user.pk:
            raise CorrectionError("You can only cancel your own request.")
        if not correction.is_pending:
            raise CorrectionError("That request has already been dealt with.")
        correction.status = AttendanceCorrection.Status.CANCELLED
        correction.decided_at = timezone.now()
        correction.save(update_fields=["status", "decided_at"])
    return correction


def pending_count(company):
    return AttendanceCorrection.objects.filter(company=company, status=AttendanceCorrection.Status.PENDING).count()

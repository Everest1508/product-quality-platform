from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.models import Membership
from apps.core.mixins import CompanyMemberRequiredMixin
from apps.dsr.forms import DSREntryForm
from apps.dsr.models import DSREntry
from apps.dsr.service import submission_window, suggestions

User = get_user_model()


def _parse_date(date_str, default):
    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return default


def _is_privileged(user, company):
    membership = Membership.objects.filter(user=user, company=company).first()
    return bool(membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN))


def _get_dsr_context(company, target_user, selected_date, is_privileged):
    today = timezone.localdate()
    prev_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)
    # Never offer a forward link past today: future days are closed to everyone.
    next_date = min(next_date, today)
    can_submit, locked_reason = submission_window(selected_date, is_privileged)

    entries = DSREntry.objects.filter(
        company=company,
        user=target_user,
        date=selected_date,
    )

    raw_total = entries.aggregate(total=Sum("hours_spent"))["total"] or Decimal("0.00")
    total_hours_float = float(raw_total)
    total_hours = f"{total_hours_float:.1f}"

    completed_count = entries.filter(status="completed").count()
    auto_logged_count = entries.filter(is_auto_logged=True).count()

    target_goal = Decimal("8.0")
    progress_percent = min(100, int((raw_total / target_goal) * 100)) if target_goal > 0 else 0

    members = User.objects.filter(memberships__company=company).order_by("username")

    team_overview = []
    if is_privileged:
        for member in members:
            m_entries = DSREntry.objects.filter(company=company, user=member, date=selected_date)
            m_raw = m_entries.aggregate(total=Sum("hours_spent"))["total"] or Decimal("0.00")
            m_hours = f"{float(m_raw):.1f}"
            m_progress = min(100, int((m_raw / target_goal) * 100))
            team_overview.append({
                "member": member,
                "total_hours": m_hours,
                "progress_percent": m_progress,
                "completed_count": m_entries.filter(status="completed").count(),
                "total_entries": m_entries.count(),
            })

    dsr_lines = [
        f"📅 DSR: {target_user.get_full_name() or target_user.username} — {selected_date.strftime('%b %d, %Y')}",
        f"⏱ Total Hours: {total_hours} hrs | Tasks Completed: {completed_count}",
        "--------------------------------------------------",
    ]
    if entries.exists():
        for idx, item in enumerate(entries, 1):
            badge = "[AUTO] " if item.is_auto_logged else ""
            cat = f" ({item.get_category_display()})"
            dsr_lines.append(f"{idx}. {badge}{item.task_name}{cat} - {item.hours_spent}h [{item.get_status_display()}]")
            if item.notes:
                dsr_lines.append(f"   Note: {item.notes}")
    else:
        dsr_lines.append("No tasks recorded for this date.")

    copy_summary_text = "\n".join(dsr_lines)

    # Open tickets assigned to this person, as one-click task names. Scoped with
    # `accessible_tickets` like every other ticket list, so a suggestion can
    # never name a ticket from a product they cannot open.
    ticket_suggestions = []
    if can_submit:
        from apps.products.access import accessible_tickets

        for t in (
            accessible_tickets(target_user, company)
            .filter(assignees=target_user, status__in=["open", "assigned", "in_progress", "testing"])
            .order_by("-id")[:6]
        ):
            ticket_suggestions.append(
                {"number": t.pk, "title": t.title, "label": f"#{t.pk} {t.title}"[:255]}
            )

    work_suggestions = suggestions(company, target_user, selected_date) if can_submit else []

    return {
        "work_suggestions": work_suggestions,
        "ticket_suggestions": ticket_suggestions,
        "selected_date": selected_date,
        "today": today,
        "yesterday": today - timedelta(days=1),
        "prev_date": prev_date,
        "next_date": next_date,
        "can_submit": can_submit,
        "locked_reason": locked_reason,
        "target_user": target_user,
        "is_privileged": is_privileged,
        "entries": entries,
        "total_hours": total_hours,
        "target_goal": target_goal,
        "progress_percent": progress_percent,
        "completed_count": completed_count,
        "auto_logged_count": auto_logged_count,
        "members": members,
        "team_overview": team_overview,
        "copy_summary_text": copy_summary_text,
        # Two prefixes: this form renders in the bar and again in the
        # empty-state row, and duplicate ids are invalid HTML.
        "add_form": DSREntryForm(id_prefix="dsr-bar"),
        "add_form_empty": DSREntryForm(id_prefix="dsr-row"),
        "category_choices": DSREntry.Category.choices,
        "status_choices": DSREntry.Status.choices,
    }


class DSRSheetView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        selected_date = _parse_date(request.GET.get("date"), today)

        is_privileged = _is_privileged(request.user, request.company)

        target_user_id = request.GET.get("user_id")
        if target_user_id and is_privileged:
            target_user = get_object_or_404(User, pk=target_user_id, memberships__company=request.company)
        else:
            target_user = request.user

        context = _get_dsr_context(request.company, target_user, selected_date, is_privileged)

        if request.headers.get("HX-Request") == "true":
            return render(request, "dsr/partials/_dsr_table.html", context)

        return render(request, "dsr/dsr_sheet.html", context)


class DSREntryUpdateView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(DSREntry, pk=pk, company=request.company)

        is_privileged = _is_privileged(request.user, request.company)
        if entry.user != request.user and not is_privileged:
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

        # Decided before any write: this POST mutates a stored sheet.
        can_submit, reason = submission_window(entry.date, is_privileged)
        if not can_submit:
            if request.headers.get("HX-Request") == "true":
                return JsonResponse({"ok": False, "error": reason}, status=403)
            messages.error(request, reason)
            return redirect(f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")

        status = request.POST.get("status", entry.status)
        category = request.POST.get("category", entry.category)

        if status not in DSREntry.Status.values:
            messages.error(request, "Unknown status.")
            status = entry.status
        if category not in DSREntry.Category.values:
            messages.error(request, "Unknown category.")
            category = entry.category

        try:
            hours = Decimal(request.POST.get("hours_spent", entry.hours_spent))
        except (ArithmeticError, ValueError, TypeError):
            messages.error(request, "Hours must be a number.")
            hours = entry.hours_spent

        form = DSREntryForm(
            {
                "task_name": request.POST.get("task_name", entry.task_name),
                "category": category,
                "hours_spent": hours,
                "status": status,
                "notes": request.POST.get("notes", entry.notes),
            },
            instance=entry,
        )
        if not form.is_valid():
            messages.error(request, "Could not save those changes.")
            entry.refresh_from_db()
        else:
            form.save()

        if request.headers.get("HX-Request") == "true":
            return render(request, "dsr/partials/_dsr_row.html", {"entry": entry, "category_choices": DSREntry.Category.choices, "status_choices": DSREntry.Status.choices})

        return redirect(f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")


class DSREntryDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(DSREntry, pk=pk, company=request.company)

        is_privileged = _is_privileged(request.user, request.company)
        if entry.user != request.user and not is_privileged:
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

        # Deleting is a mutation too, so the same window applies.
        can_submit, reason = submission_window(entry.date, is_privileged)
        if not can_submit:
            if request.headers.get("HX-Request") == "true":
                return JsonResponse({"ok": False, "error": reason}, status=403)
            messages.error(request, reason)
            return redirect(f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")

        entry_date = entry.date
        target_user = entry.user
        task_name = entry.task_name
        entry.delete()
        messages.success(request, f"Deleted \"{task_name}\".")

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, entry_date, is_privileged)
            return render(request, "dsr/partials/_dsr_table.html", context)

        return redirect(f"/dsr/?date={entry_date.isoformat()}&user_id={target_user.id}")


class DSREntryAddView(CompanyMemberRequiredMixin, View):
    def post(self, request):
        today = timezone.localdate()
        target_date = _parse_date(request.GET.get("date") or request.POST.get("date"), today)

        is_privileged = _is_privileged(request.user, request.company)

        target_user_id = request.GET.get("user_id") or request.POST.get("user_id")
        if target_user_id and is_privileged:
            target_user = get_object_or_404(User, pk=target_user_id, memberships__company=request.company)
        else:
            target_user = request.user

        # `date` arrives from the query string, so this is the one place that
        # has to refuse a day the sheet cannot accept rather than trust the UI.
        can_submit, reason = submission_window(target_date, is_privileged)
        if not can_submit:
            messages.error(request, reason)
            if request.headers.get("HX-Request") == "true":
                context = _get_dsr_context(request.company, target_user, target_date, is_privileged)
                return render(request, "dsr/partials/_dsr_table.html", context)
            return redirect(f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")

        form = DSREntryForm(request.POST, id_prefix="dsr-bar")
        if form.is_valid():
            entry = form.save(commit=False)
            entry.company = request.company
            entry.user = target_user
            entry.date = target_date
            entry.is_auto_logged = False
            entry.save()
            messages.success(request, f"Added \"{entry.task_name}\".")
        else:
            messages.error(request, "Could not add that entry.")

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, target_date, is_privileged)
            context["add_form"] = form
            context["add_form_empty"] = DSREntryForm(id_prefix="dsr-row")
            return render(request, "dsr/partials/_dsr_table.html", context)

        return redirect(f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")



class DSRSuggestionAddView(CompanyMemberRequiredMixin, View):
    """Log one suggested ticket with the hours the person confirms.

    Only a ticket the sheet actually suggested can be added, so this cannot be
    used to log arbitrary tickets, and the day's submission window applies exactly
    as it does for a manual entry.
    """

    def post(self, request):
        today = timezone.localdate()
        target_date = _parse_date(request.GET.get("date") or request.POST.get("date"), today)
        is_privileged = _is_privileged(request.user, request.company)
        target_user_id = request.GET.get("user_id") or request.POST.get("user_id")
        if target_user_id and is_privileged:
            target_user = get_object_or_404(User, pk=target_user_id, memberships__company=request.company)
        else:
            target_user = request.user

        def respond():
            if request.headers.get("HX-Request") == "true":
                context = _get_dsr_context(request.company, target_user, target_date, is_privileged)
                return render(request, "dsr/partials/_dsr_table.html", context)
            return redirect(f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")

        can_submit, reason = submission_window(target_date, is_privileged)
        if not can_submit:
            messages.error(request, reason)
            return respond()

        try:
            ticket_id = int(request.POST.get("ticket_id", ""))
            hours = Decimal(request.POST.get("hours", ""))
        except (ValueError, ArithmeticError):
            messages.error(request, "Enter the hours as a number.")
            return respond()
        # NaN and Infinity parse as Decimals and blow up on comparison, so they are
        # refused before the range check.
        if not hours.is_finite() or hours <= 0 or hours > 24:
            messages.error(request, "Hours must be more than 0 and at most 24.")
            return respond()

        match = next(
            (r for r in suggestions(request.company, target_user, target_date, limit=50) if r["number"] == ticket_id),
            None,
        )
        if match is None:
            messages.error(request, "That ticket is not in your suggestions for this day.")
            return respond()

        ticket = match["ticket"]
        DSREntry.objects.create(
            company=request.company,
            user=target_user,
            date=target_date,
            ticket=ticket,
            task_name=f"#{ticket.pk} {ticket.title}"[:255],
            category=match["category"],
            hours_spent=hours.quantize(Decimal("0.01")),
            status=match["status"],
            is_auto_logged=False,
        )
        messages.success(request, f"Added #{ticket.pk} with {hours.normalize():f}h.")
        return respond()

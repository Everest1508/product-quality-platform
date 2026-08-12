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
from apps.dsr.models import DSREntry

User = get_user_model()


def _parse_date(date_str, default):
    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return default


def _get_dsr_context(company, target_user, selected_date, is_privileged):
    today = timezone.localdate()
    prev_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)

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

    return {
        "selected_date": selected_date,
        "today": today,
        "yesterday": today - timedelta(days=1),
        "prev_date": prev_date,
        "next_date": next_date,
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
        "category_choices": DSREntry.Category.choices,
        "status_choices": DSREntry.Status.choices,
    }


class DSRSheetView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        selected_date = _parse_date(request.GET.get("date"), today)

        membership = Membership.objects.filter(user=request.user, company=request.company).first()
        is_privileged = bool(
            membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )

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

        membership = Membership.objects.filter(user=request.user, company=request.company).first()
        is_privileged = bool(
            membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )
        if entry.user != request.user and not is_privileged:
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

        if "hours_spent" in request.POST:
            try:
                entry.hours_spent = Decimal(request.POST.get("hours_spent", "0"))
            except Exception:
                pass

        if "notes" in request.POST:
            entry.notes = request.POST.get("notes", "")

        if "status" in request.POST:
            entry.status = request.POST.get("status", entry.status)

        if "task_name" in request.POST:
            entry.task_name = request.POST.get("task_name", entry.task_name)

        if "category" in request.POST:
            entry.category = request.POST.get("category", entry.category)

        entry.save()

        if request.headers.get("HX-Request") == "true":
            return render(request, "dsr/partials/_dsr_row.html", {"entry": entry, "category_choices": DSREntry.Category.choices, "status_choices": DSREntry.Status.choices})

        return redirect(f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")


class DSREntryDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        entry = get_object_or_404(DSREntry, pk=pk, company=request.company)

        membership = Membership.objects.filter(user=request.user, company=request.company).first()
        is_privileged = bool(
            membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )
        if entry.user != request.user and not is_privileged:
            return JsonResponse({"ok": False, "error": "Permission denied"}, status=403)

        entry_date = entry.date
        target_user = entry.user
        entry.delete()

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, entry_date, is_privileged)
            return render(request, "dsr/partials/_dsr_table.html", context)

        return redirect(f"/dsr/?date={entry_date.isoformat()}&user_id={target_user.id}")


class DSREntryAddView(CompanyMemberRequiredMixin, View):
    def post(self, request):
        today = timezone.localdate()
        target_date = _parse_date(request.GET.get("date") or request.POST.get("date"), today)

        membership = Membership.objects.filter(user=request.user, company=request.company).first()
        is_privileged = bool(
            membership and membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)
        )

        target_user_id = request.GET.get("user_id") or request.POST.get("user_id")
        if target_user_id and is_privileged:
            target_user = get_object_or_404(User, pk=target_user_id, memberships__company=request.company)
        else:
            target_user = request.user

        entry = DSREntry.objects.create(
            company=request.company,
            user=target_user,
            date=target_date,
            task_name="New Task",
            category=DSREntry.Category.OTHER,
            hours_spent=Decimal("1.00"),
            status=DSREntry.Status.COMPLETED,
            is_auto_logged=False,
        )

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, target_date, is_privileged)
            return render(request, "dsr/partials/_dsr_table.html", context)

        return redirect(f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")

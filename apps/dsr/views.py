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
from apps.dashboards.service import log_activity
from apps.dsr.duration import MESSAGE, format_hm, parse_hours
from apps.dsr.forms import DSREntryForm
from apps.dsr.models import DSREntry
from apps.dsr.service import submission_window, suggestions

User = get_user_model()


def _back(request, fallback):
    """Where to go after a write: the page it was made from (a site-relative `next`), else the sheet for that day."""
    from apps.core.redirects import safe_next

    return redirect(safe_next(request.POST.get("next")) or fallback)


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

    from apps.products.access import accessible_products

    products = accessible_products(target_user, company).order_by("name")
    entries = DSREntry.objects.filter(
        company=company,
        user=target_user,
        date=selected_date,
    ).select_related("product", "ticket")

    raw_total = entries.aggregate(total=Sum("hours_spent"))["total"] or Decimal("0.00")
    total_hours = raw_total

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
            m_progress = min(100, int((m_raw / target_goal) * 100))
            team_overview.append({
                "member": member,
                "total_hours": m_raw,
                "progress_percent": m_progress,
                "completed_count": m_entries.filter(status="completed").count(),
                "total_entries": m_entries.count(),
            })

    dsr_lines = [
        f"📅 DSR: {target_user.get_full_name() or target_user.username} — {selected_date.strftime('%b %d, %Y')}",
        f"⏱ Total Time: {format_hm(total_hours)} | Tasks Completed: {completed_count}",
        "--------------------------------------------------",
    ]
    if entries.exists():
        for idx, item in enumerate(entries, 1):
            badge = "[AUTO] " if item.is_auto_logged else ""
            cat = f" ({item.get_category_display()})"
            # Ticket entries already name the product in their text.
            where = f"[{item.product.name}] " if item.product and f"[{item.product.name}]" not in item.task_name else ""
            dsr_lines.append(f"{idx}. {badge}{where}{item.task_name}{cat} - {format_hm(item.hours_spent)} [{item.get_status_display()}]")
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
            accessible_tickets(target_user, company).select_related("product")
            .filter(assignees=target_user, status__in=["open", "assigned", "in_progress", "testing"])
            .order_by("-id")[:6]
        ):
            ticket_suggestions.append(
                {"number": t.pk, "key": t.key, "title": t.title, "label": f"{t.key} {t.title}"[:255]}
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
        "products": products,
        "add_form": DSREntryForm(id_prefix="dsr-bar", products=products),
        "add_form_empty": DSREntryForm(id_prefix="dsr-row", products=products),
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
            return _back(request, f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")

        status = request.POST.get("status", entry.status)
        category = request.POST.get("category", entry.category)

        if status not in DSREntry.Status.values:
            messages.error(request, "Unknown status.")
            status = entry.status
        if category not in DSREntry.Category.values:
            messages.error(request, "Unknown category.")
            category = entry.category

        from apps.products.access import accessible_products

        products = accessible_products(entry.user, request.company)
        form = DSREntryForm(
            {
                "task_name": request.POST.get("task_name", entry.task_name),
                # Only a manual row posts a product; a ticket's row keeps its own.
                "product": request.POST.get("product", entry.product_id or ""),
                "category": category,
                "hours_spent": request.POST.get("hours_spent", entry.hours_spent),
                "status": status,
                "notes": request.POST.get("notes", entry.notes),
            },
            instance=entry,
            products=products,
        )
        if not form.is_valid():
            messages.error(request, "Could not save those changes.")
            entry.refresh_from_db()
        else:
            form.save()
            log_activity(
                request.company, "dsr_entry_updated",
                f"{entry.task_name} updated on the DSR",
                description=f"{entry.date} · {entry.hours_spent}h · {entry.get_status_display()}",
                actor=request.user,
                metadata={
                    "user_id": entry.user_id,
                    "date": entry.date.isoformat(),
                    "product_id": entry.product_id,
                },
            )

        if request.headers.get("HX-Request") == "true":
            return render(request, "dsr/partials/_dsr_row.html", {"entry": entry, "can_submit": True, "products": products.order_by("name"), "category_choices": DSREntry.Category.choices, "status_choices": DSREntry.Status.choices})

        return _back(request, f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")


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
            return _back(request, f"/dsr/?date={entry.date.isoformat()}&user_id={entry.user.id}")

        entry_date = entry.date
        target_user = entry.user
        task_name = entry.task_name
        hours = entry.hours_spent
        entry.delete()
        messages.success(request, f"Deleted \"{task_name}\".")
        log_activity(
            request.company, "dsr_entry_deleted",
            f"\"{task_name}\" removed from the DSR",
            description=f"{entry_date} · {hours}h",
            actor=request.user,
            metadata={"user_id": target_user.pk, "date": entry_date.isoformat()},
        )

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, entry_date, is_privileged)
            return render(request, "dsr/partials/_dsr_table.html", context)

        return _back(request, f"/dsr/?date={entry_date.isoformat()}&user_id={target_user.id}")


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
            return _back(request, f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")

        from apps.products.access import accessible_products

        products = accessible_products(target_user, request.company).order_by("name")
        form = DSREntryForm(request.POST, id_prefix="dsr-bar", products=products)
        saved = form.is_valid()
        if saved:
            entry = form.save(commit=False)
            entry.company = request.company
            entry.user = target_user
            entry.date = target_date
            entry.is_auto_logged = False
            entry.save()
            messages.success(request, f"Added \"{entry.task_name}\".")
            log_activity(
                request.company, "dsr_entry_added",
                f"{entry.task_name} logged",
                description=f"{entry.date} · {entry.category} · {entry.hours_spent}h",
                actor=request.user,
                metadata={
                    "user_id": entry.user_id,
                    "date": entry.date.isoformat(),
                    "product_id": entry.product_id,
                },
            )
        else:
            messages.error(request, "Could not add that entry.")

        if request.headers.get("HX-Request") == "true":
            context = _get_dsr_context(request.company, target_user, target_date, is_privileged)
            # After a save the form starts empty, so the next entry does not open
            # with the last one's text. After a failure it keeps what was typed,
            # with the errors. Either way it stays open for the next entry.
            if not saved:
                context["add_form"] = form
            context["add_open"] = True
            return render(request, "dsr/partials/_dsr_table.html", context)

        return _back(request, f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")



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
            return _back(request, f"/dsr/?date={target_date.isoformat()}&user_id={target_user.id}")

        can_submit, reason = submission_window(target_date, is_privileged)
        if not can_submit:
            messages.error(request, reason)
            return respond()

        try:
            ticket_id = int(request.POST.get("ticket_id", ""))
            hours = parse_hours(request.POST.get("hours", ""))
        except ValueError:
            messages.error(request, MESSAGE + ".")
            return respond()
        if hours is None or hours <= 0 or hours > 24:
            messages.error(request, "Time must be more than 0 and at most 24 hours.")
            return respond()

        match = next(
            (r for r in suggestions(request.company, target_user, target_date, limit=50) if r["number"] == ticket_id),
            None,
        )
        if match is None:
            messages.error(request, "That ticket is not in your suggestions for this day.")
            return respond()

        ticket = match["ticket"]
        entry = DSREntry.objects.create(
            company=request.company,
            user=target_user,
            date=target_date,
            ticket=ticket,
            product=ticket.product,
            task_name=f"{ticket.key} {ticket.title}"[:255],
            category=match["category"],
            hours_spent=hours.quantize(Decimal("0.01")),
            status=match["status"],
            is_auto_logged=False,
        )
        messages.success(request, f"Added {ticket.key} with {format_hm(hours)}.")
        log_activity(
            request.company, "dsr_entry_added",
            f"{entry.task_name} logged",
            description=f"{entry.date} · {entry.category} · {entry.hours_spent}h",
            actor=request.user,
            metadata={
                "user_id": entry.user_id,
                "date": entry.date.isoformat(),
                "product_id": entry.product_id,
            },
        )
        return respond()


class DSRLogView(CompanyMemberRequiredMixin, View):
    """Everything submitted, today and before, as one table: grouped by day, searchable, with a CSV export.

    `range` is today, yesterday, 7d (default) or 30d; `date` shows one day. Owners and admins can pass `user_id` (a member, or
    `all`). Everybody else only ever sees their own rows."""

    MAX_ROWS = 500

    def get(self, request):
        today = timezone.localdate()
        params = request.GET
        rng = params.get("range", "7d")
        one_day = _parse_date(params.get("date"), None)
        if one_day:
            start = end = min(one_day, today)
            rng = "day"
        else:
            start, end = {
                "today": (today, today),
                "yesterday": (today - timedelta(days=1),) * 2,
                "30d": (today - timedelta(days=29), today),
            }.get(rng, (today - timedelta(days=6), today))
            if rng not in ("today", "yesterday", "30d"):
                rng = "7d"
        privileged = _is_privileged(request.user, request.company)
        who = params.get("user_id", "")
        everyone = privileged and who == "all"
        if privileged and who and who != "all":
            target = get_object_or_404(User, pk=who, memberships__company=request.company)
        else:
            target = request.user
        qs = DSREntry.objects.filter(company=request.company, date__gte=start, date__lte=end).select_related("user", "product", "ticket", "ticket__product")
        if not everyone:
            qs = qs.filter(user=target)
        q = (params.get("q") or "").strip()
        if q:
            from django.db.models import Q

            qs = qs.filter(Q(task_name__icontains=q) | Q(notes__icontains=q) | Q(product__name__icontains=q))
        total_rows = qs.count()
        entries = list(qs.order_by("-date", "user__username", "-created_at")[: self.MAX_ROWS])

        if params.get("export") == "csv":
            from apps.core.csvx import csv_response

            return csv_response(
                f"dsr-{start}-to-{end}.csv", ["Date", "Employee", "Task", "Project", "Category", "Hours", "Status", "Notes"],
                [[e.date.isoformat(), e.user.get_full_name() or e.user.username, e.task_name, e.product.name if e.product else "", e.get_category_display(), e.hours_spent, e.get_status_display(), e.notes] for e in entries],
            )

        days, lines = {}, []
        for e in entries:
            can_change = (e.user_id == request.user.pk or privileged) and submission_window(e.date, privileged)[0]
            e.can_change = can_change
            e.person = e.user.get_full_name() or e.user.username
            e.elapsed = _elapsed(e)
            d = days.setdefault(e.date, {"date": e.date, "rows": [], "hours": Decimal("0.00")})
            d["rows"].append(e)
            d["hours"] += e.hours_spent
        day_list = list(days.values())
        total = sum((d["hours"] for d in day_list), Decimal("0.00"))
        for d in day_list:
            d["hours_label"] = format_hm(d["hours"]) if d["hours"] else "0m"
            d["is_today"] = d["date"] == today
            lines.append(f"📅 {d['date'].strftime('%a, %-d %b')}: {format_hm(d['hours'])}, {len(d['rows'])} task{'s' if len(d['rows']) != 1 else ''}")
        for e in entries:
            lines.append(f"- {e.date.strftime('%-d %b')} {e.person + ': ' if everyone else ''}{e.task_name} ({e.get_category_display()}) - {format_hm(e.hours_spent)} [{e.get_status_display()}]")

        waiting = [e for e in entries if e.needs_time and e.can_change]
        can_log, locked = submission_window(today, privileged)
        from apps.products.access import accessible_products

        products = accessible_products(target, request.company).order_by("name")
        can_log_here = can_log and (target == request.user or privileged)
        return render(request, "dsr/dsr_log.html", {
            "rng": rng, "start": start, "end": end, "today": today, "q": q, "everyone": everyone, "target": target,
            "privileged": privileged, "who": "all" if everyone else (str(target.pk) if target != request.user else ""),
            "members": User.objects.filter(memberships__company=request.company).order_by("username") if privileged else [],
            "days": day_list, "count": len(entries), "completed": sum(1 for e in entries if e.status == "completed"),
            "total_label": format_hm(total) if total else "0m", "truncated": total_rows > self.MAX_ROWS,
            "summary_text": "\n".join(lines) if entries else "No tasks recorded for this period.",
            "can_log": can_log_here, "locked_reason": locked, "products": products,
            "categories": DSREntry.Category.choices, "statuses": DSREntry.Status.choices,
            "waiting": waiting,
            "work_suggestions": suggestions(request.company, target, today) if can_log_here and rng in ("today", "7d", "30d", "yesterday") else [],
        })


def _elapsed(e):
    """How long the ticket behind an auto-logged row was open ("3h 20m", or "11d 1h" past two days). Empty when unknown."""
    from apps.dsr.service import elapsed_label

    return elapsed_label(e)


class DSRSuggestionAddAllView(CompanyMemberRequiredMixin, View):
    """One click: log everything the sheet suggests for today at the suggested hours."""

    def post(self, request):
        from apps.dsr.service import add_all_suggested

        today = timezone.localdate()
        privileged = _is_privileged(request.user, request.company)
        who = request.GET.get("user_id") or request.POST.get("user_id")
        target = get_object_or_404(User, pk=who, memberships__company=request.company) if who and privileged else request.user
        ok, reason = submission_window(today, privileged)
        if not ok:
            messages.error(request, reason)
        else:
            entries, message = add_all_suggested(request.company, request.user, target, today)
            (messages.success if entries else messages.error)(request, message)
        return _back(request, "/dsr/")

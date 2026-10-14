"""Pages for a project's life: the board and journey of every project, one project's lifecycle and details.

The rules (who may move, the reason, skipped phases, the log, who is told) live in `lifecycle.py`; these views
only read the request, call it, and show the result.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.dashboards.service import log_activity
from apps.products import lifecycle as lc
from apps.products.access import accessible_products, product_users, require_product_access
from apps.products.models import CrunchItem, Product

KIND_FILTERS = [("", "Everything"), ("update", "Updates"), ("stage", "Stage changes"), ("blocker", "Blockers"),
                ("decision", "Decisions"), ("crunch", "Crunch"), ("schedule", "Schedule")]


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")


def _respond(request, ok, text, back):
    """JSON for the drag and drop and dialog scripts, a redirect with a toast for plain forms."""
    (messages.success if ok else messages.error)(request, text)
    if _wants_json(request):
        return JsonResponse({"ok": ok, "message": text}, status=200 if ok else 400)
    return redirect(back)


def _int_or_none(value):
    return int(value) if str(value or "").isdigit() else None


def _card(product, today):
    """What one project card or journey row needs, worked out once."""
    enabled = lc.enabled_phases(product)
    here = lc.current_stage(product)
    plans = {p.phase: p for p in product.phase_plans.all()}
    plan_now = plans.get(here)
    late_days = 0
    if plan_now and plan_now.end_date and plan_now.end_date < today and here not in ("live", "close"):
        late_days = (today - plan_now.end_date).days
    crunch = [c for c in product.crunch_items.all() if not c.done]
    next_crunch = min(crunch, key=lambda c: c.due_date) if crunch else None
    return {
        "product": product, "stage": here, "stage_label": lc.LABELS[here], "enabled": enabled, "days": lc.days_in_stage(product),
        "pod": lc.pod_users(product), "late_days": late_days, "plans": plans,
        "crunch_open": len(crunch), "next_crunch": next_crunch,
        "next_crunch_state": lc.crunch_state(next_crunch, today) if next_crunch else "",
        "off_json": ",".join(k for k in lc.KEYS if k not in enabled),
    }


def _journey(card, product):
    """Nine nodes for one project: done, current, upcoming or not used, with the date each was entered."""
    reached = {}
    for seg in lc.history(product):
        reached.setdefault(seg["stage"], seg)
    nodes = []
    for key, label in lc.STAGES:
        plan = card["plans"].get(key)
        state = "off" if key not in card["enabled"] else "now" if key == card["stage"] else "done" if key in reached and key != card["stage"] else "next"
        nodes.append({"key": key, "label": label, "state": state, "since": reached.get(key, {}).get("start"),
                      "days": reached.get(key, {}).get("days"), "plan": plan})
    return nodes


class ProjectsBoardView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        products = (accessible_products(request.user, request.company)
                    .select_related("lead").prefetch_related("phase_plans", "crunch_items", "pod_members__user")
                    .order_by("name"))
        today = timezone.localdate()
        cards = [_card(p, today) for p in products]
        view = "journey" if request.GET.get("view") == "journey" else "board"
        columns = [{"key": k, "label": l, "cards": [c for c in cards if c["stage"] == k]} for k, l in lc.STAGES]
        rows = []
        if view == "journey":
            rows = [{"card": c, "nodes": _journey(c, c["product"])} for c in cards]
        return render(request, "products/projects_board.html", {
            "view": view, "columns": columns, "rows": rows, "total": len(cards),
            "can_add": request.company_role in ("owner", "admin"), "stages": lc.STAGES,
        })


class ProjectQuickAddView(CompanyAdminRequiredMixin, View):
    """`+ Add project` at the foot of a column: a name, and it starts in that phase."""

    def post(self, request):
        name = request.POST.get("name", "").strip()[:255]
        stage = request.POST.get("stage", "creation")
        back = "products:project_board"
        if not name:
            return _respond(request, False, "Give the project a name.", back)
        if stage not in lc.LABELS:
            stage = "creation"
        slug = base = slugify(name) or "project"
        n = 2
        while Product.objects.filter(company=request.company, slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        product = Product.objects.create(company=request.company, name=name, slug=slug, stage=stage,
                                         stage_changed_at=timezone.now(), lead=request.user)
        lc.set_team(product, request.user, [], request.user)
        lc._log(product, request.user, "setup", f"Project created in {lc.LABELS[stage]}.")
        log_activity(request.company, "product_created", f"Product '{product.name}' created", actor=request.user,
                     target_content_type="product", target_object_id=product.pk)
        return _respond(request, True, f"{name} added in {lc.LABELS[stage]}.", back)


class ProjectMoveView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        back = request.POST.get("next") or "products:project_board"
        try:
            lc.move_stage(product, request.POST.get("to", ""), request.POST.get("reason", ""), request.user, request.company_role)
        except lc.LifecycleError as exc:
            return _respond(request, False, str(exc), back)
        return _respond(request, True, f"{product.name} moved to {lc.LABELS[product.stage]}.", back)


def _members(request, product=None):
    User = get_user_model()
    if product is not None:
        return product_users(product, request.company)
    return User.objects.filter(memberships__company=request.company).order_by("username").distinct()


class ProjectLifecycleView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        kind = request.GET.get("kind", "")
        who = _int_or_none(request.GET.get("who"))
        entries = product.log_entries.select_related("author").prefetch_related("mentions")
        if request.GET.get("mine") == "1":
            entries = entries.filter(mentions=request.user)
        if kind in dict(KIND_FILTERS) and kind:
            entries = entries.filter(kind=kind)
        if who:
            entries = entries.filter(author_id=who)
        today = timezone.localdate()
        card = _card(product, today)
        segs = lc.history(product)
        by_stage = {}
        for s in segs:
            by_stage[s["stage"]] = by_stage.get(s["stage"], 0) + s["days"]
        return render(request, "products/project_lifecycle.html", {
            "product": product, "card": card, "nodes": _journey(card, product), "entries": entries[:200],
            "can_work": lc.can_work(request.user, product, request.company_role), "next_stage": lc.next_stage(product),
            "kind": kind, "kind_filters": KIND_FILTERS, "who": who, "mine": request.GET.get("mine") == "1",
            "pod": card["pod"], "stage_days": [(k, l, by_stage.get(k, 0), card["plans"].get(k)) for k, l in lc.STAGES if k in card["enabled"]],
            "crunch": [(c, lc.crunch_state(c, today)) for c in product.crunch_items.all()],
            "mention_people": [{"username": u.username, "name": u.get_full_name() or u.username} for u in card["pod"]],
            "stages": lc.STAGES, "labels": lc.LABELS,
            "compose_kinds": [("update", "Update"), ("blocker", "Blocker"), ("decision", "Decision"), ("correction", "Correction")],
        })


class ProjectLogAddView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        back = redirect_url(product)
        try:
            lc.add_entry(product, request.user, request.company_role, request.POST.get("kind", "update"), request.POST.get("body", ""))
        except lc.LifecycleError as exc:
            return _respond(request, False, str(exc), back)
        return _respond(request, True, "Added to the log.", back)


def redirect_url(product):
    from django.urls import reverse

    return reverse("products:project_lifecycle", kwargs={"pk": product.pk})


def _schedule_from(post):
    rows = {}
    for key in lc.KEYS:
        row = {"start": post.get(f"s_{key}"), "end": post.get(f"e_{key}"), "hours": post.get(f"h_{key}")}
        if any(row.values()):
            rows[key] = row
    return rows


def _team_from(request, post):
    ids = {int(i) for i in post.getlist("pod") if str(i).isdigit()}
    lead_id = _int_or_none(post.get("lead"))
    users = {u.pk: u for u in _members(request).filter(pk__in=ids | ({lead_id} if lead_id else set()))}
    return users.get(lead_id), [users[i] for i in ids if i in users]


class ProjectDetailsView(CompanyMemberRequiredMixin, View):
    """The plan: dates, Pod, stack, SRS, phases, schedule and Crunch items."""

    def _context(self, request, product, error=""):
        today = timezone.localdate()
        card = _card(product, today)
        return {
            "product": product, "card": card, "members": _members(request), "error": error, "stages": lc.STAGES,
            "can_work": lc.can_work(request.user, product, request.company_role), "presets": lc.PRESETS,
            "pod_ids": {u.pk for u in card["pod"]}, "plans": card["plans"],
            "crunch": [(c, lc.crunch_state(c, today)) for c in product.crunch_items.all()],
            "rows": [(k, l, k in card["enabled"], card["plans"].get(k)) for k, l in lc.STAGES],
            "on_map": {k: k in card["enabled"] for k, _ in lc.STAGES},
        }

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render(request, "products/project_details.html", self._context(request, product))

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        if not lc.can_work(request.user, product, request.company_role):
            messages.error(request, "Only the project lead, the Pod, owners and admins can change the plan.")
            return redirect("products:project_details", pk=pk)
        post = request.POST
        phases = [k for k in lc.KEYS if post.get(f"phase_{k}")]
        tags = [t for t in post.get("tech_stack", "").replace("\n", ",").split(",")]
        try:
            lc.save_plan(product, user=request.user, start=post.get("start_date"), end=post.get("end_date"),
                         tech_stack=tags, srs=post.get("srs", ""), phases=phases, schedule=_schedule_from(post))
            if request.company_role in ("owner", "admin") or lc.is_pod(request.user, product):
                lead, members = _team_from(request, post)
                lc.set_team(product, lead, members, request.user)
        except lc.LifecycleError as exc:
            product.refresh_from_db()
            return render(request, "products/project_details.html", self._context(request, product, str(exc)), status=400)
        messages.success(request, "Project plan saved.")
        return redirect("products:project_details", pk=pk)


class ProjectCrunchAddView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        back = redirect_url(product)
        try:
            lc.add_crunch(product, request.user, request.company_role, request.POST.get("feature"), request.POST.get("due"), request.POST.get("reason", ""))
        except lc.LifecycleError as exc:
            return _respond(request, False, str(exc), request.POST.get("next") or back)
        return _respond(request, True, "Crunch item added.", request.POST.get("next") or back)


class ProjectCrunchDoneView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(CrunchItem, pk=pk, company=request.company)
        require_product_access(request, item.product)
        try:
            lc.finish_crunch(item, request.user, request.company_role)
        except lc.LifecycleError as exc:
            return _respond(request, False, str(exc), redirect_url(item.product))
        return _respond(request, True, f"{item.feature} marked done.", request.POST.get("next") or redirect_url(item.product))


class ProjectNewView(CompanyAdminRequiredMixin, View):
    """Create a project with its whole plan in one go (owners and admins create products)."""

    def get(self, request):
        stub = Product(company=request.company, name="", stage="creation", phases=[])
        return render(request, "products/project_new.html", {
            "members": _members(request), "stages": lc.STAGES, "presets": lc.PRESETS, "error": "", "posted": {},
            "rows": [(k, l, True, None) for k, l in lc.STAGES], "pod_ids": {request.user.pk}, "stub": stub,
            "on_map": {k: True for k, _ in lc.STAGES},
        })

    def post(self, request):
        post = request.POST
        name = post.get("name", "").strip()[:255]
        phases = [k for k in lc.KEYS if post.get(f"phase_{k}")]
        lead, members = _team_from(request, post)

        def again(error):
            return render(request, "products/project_new.html", {
                "members": _members(request), "stages": lc.STAGES, "presets": lc.PRESETS, "error": error, "posted": post,
                "rows": [(k, l, k in phases or not phases, None) for k, l in lc.STAGES],
                "on_map": {k: (k in phases or not phases) for k, _ in lc.STAGES},
                "pod_ids": {m.pk for m in members}, "stub": Product(name=name),
            }, status=400)

        if not name:
            return again("Give the project a name.")
        slug = base = slugify(name) or "project"
        n = 2
        while Product.objects.filter(company=request.company, slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        first = (phases or lc.KEYS)[0]
        from django.db import transaction

        try:
            with transaction.atomic():
                product = Product.objects.create(company=request.company, name=name, slug=slug, description=post.get("description", "")[:2000],
                                                 stage=first, stage_changed_at=timezone.now())
                lc.save_plan(product, user=request.user, start=post.get("start_date"), end=post.get("end_date"),
                             tech_stack=post.get("tech_stack", "").replace("\n", ",").split(","), srs=post.get("srs", ""),
                             phases=phases or lc.KEYS, schedule=_schedule_from(post))
                lc.set_team(product, lead or request.user, members, request.user)
                lc._log(product, request.user, "setup", f"Project created, starting in {lc.LABELS[first]}.")
                for feature, due, reason in zip(post.getlist("crunch_feature"), post.getlist("crunch_due"), post.getlist("crunch_reason")):
                    if feature.strip():
                        lc.add_crunch(product, request.user, request.company_role, feature, due, reason)
        except lc.LifecycleError as exc:
            return again(str(exc))
        log_activity(request.company, "product_created", f"Product '{product.name}' created", actor=request.user,
                     target_content_type="product", target_object_id=product.pk)
        messages.success(request, f"{product.name} created.")
        return redirect("products:project_lifecycle", pk=product.pk)

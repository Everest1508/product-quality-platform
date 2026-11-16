from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import render
from django.views import View
from django.utils import timezone

from apps.core.mixins import CompanyAdminRequiredMixin

from . import exports
from .registry import GROUPS, PERIODS, REPORTS, Ctx, period_dates, visible

ROW_LIMIT = 500


def _parse(raw):
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def show(v):
    """(text, is_number) for one table cell."""
    if v is None or v == "":
        return "—", False
    if isinstance(v, datetime):
        t = timezone.localtime(v) if timezone.is_aware(v) else v
        return f"{t:%d %b %Y}, {t:%I:%M %p}".replace(" 0", " "), False
    if isinstance(v, date):
        return f"{v:%d %b %Y}".lstrip("0"), False
    if isinstance(v, (int, Decimal)) and not isinstance(v, bool):
        return f"{v:,}", True
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip("."), True
    return str(v), False


class HubView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        admin = request.company_role in ("owner", "admin")
        mine = visible(admin)
        groups = []
        for key, label, icon in GROUPS:
            items = sorted((r for r in mine if r.group == key), key=lambda r: r.title)
            if items:
                groups.append({"key": key, "label": label, "icon": icon, "reports": items})
        return render(request, "reports/hub.html", {"groups": groups, "total": len(mine), "is_admin": admin})


class RunView(CompanyAdminRequiredMixin, View):
    def context(self, request, key):
        rep = REPORTS.get(key)
        admin = request.company_role in ("owner", "admin")
        if not rep or (rep.admin and not admin):
            raise Http404
        g = request.GET
        today = timezone.localdate()
        preset = g.get("period") if g.get("period") in dict(PERIODS) else ""
        start, end = _parse(g.get("start")), _parse(g.get("end"))
        if preset or not (start and end):
            start, end = period_dates(preset or "30d", today)
        if start > end:
            start, end = end, start
        ctx = Ctx(user=request.user, company=request.company, start=start, end=end, is_admin=admin)
        if "product" in rep.filters and g.get("product", "").isdigit():
            ctx.product = ctx.products.filter(pk=g["product"]).first()
        if "person" in rep.filters and admin and g.get("person", "").isdigit():
            ctx.person = get_user_model().objects.filter(pk=g["person"], memberships__company=request.company).first()
        return rep, ctx, preset

    def get(self, request, key):
        rep, ctx, preset = self.context(request, key)
        result = rep.run(ctx)
        fmt = request.GET.get("export")
        if fmt == "xlsx":
            return exports.xlsx_file(rep, ctx, result)
        if fmt == "csv":
            return exports.csv_file(rep, ctx, result)
        total = len(result.rows)
        shown = [[show(c) for c in r] for r in result.rows[:ROW_LIMIT]]
        keep = request.GET.copy()
        keep.pop("export", None)
        return render(request, "reports/run.html", {
            "rep": rep, "ctx": ctx, "result": result, "rows": shown, "total": total, "limit": ROW_LIMIT,
            "periods": PERIODS, "preset": preset if preset else ("" if request.GET.get("start") else "30d"),
            "products": ctx.products.order_by("name") if "product" in rep.filters else [],
            "people": (get_user_model().objects.filter(memberships__company=request.company).order_by("username")
                       if "person" in rep.filters and ctx.is_admin else []),
            "query": keep.urlencode(),
            "group_label": dict((k, l) for k, l, _ in GROUPS).get(rep.group, ""),
        })

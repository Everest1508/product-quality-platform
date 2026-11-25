"""Staff pages for backed-up CardSnap cards: read-only, and every visit (list, search, detail, export) is logged."""
import csv
from datetime import timedelta
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q, TextField
from django.db.models.functions import Cast, Lower
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from apps.appauth.models import AppCard, AppCardAccessLog, AppUser
from apps.appauth.web import _is_date, _safe_cell
from apps.core.mixins import CompanyAdminRequiredMixin
from apps.core.pagination import DEFAULT_PAGE_SIZE, PAGE_SIZES

FILTERS = ("user", "exhibition", "from", "to", "multi")
PER_PAGE_KEY = "appauth_cards_per_page"
MAX_CHOICES = 300  # owner and exhibition lists in the filter bar


def _audit(request, action, app_user=None, detail=""):
    AppCardAccessLog.objects.create(
        staff=request.user, staff_email=request.user.email, app_user=app_user,
        app_user_email=app_user.email if app_user else "", action=action, detail=detail[:200])


def _label(u):
    return u.name or u.email


def _per_page(request):
    """Rows per page, remembered for this browser session once the person picks one."""
    asked = request.GET.get("per_page", "")
    if asked in {str(n) for n in PAGE_SIZES}:
        request.session[PER_PAGE_KEY] = int(asked)
    return request.session.get(PER_PAGE_KEY, DEFAULT_PAGE_SIZE)


def _page(request, qs):
    return Paginator(qs, _per_page(request)).get_page(request.GET.get("page", 1))


def _order(sort):
    """(expression list, the sort key that was actually used). Name and company ignore case."""
    key = sort if sort.lstrip("-") in ("updated", "name", "company", "owner") else "-updated"
    col = {"updated": F("updated_at"), "name": Lower("name"), "company": Lower("company"), "owner": Lower("user__email")}[key.lstrip("-")]
    first = col.desc() if key.startswith("-") else col.asc()
    return [first, "-updated_at", "id"], key


def _cards(request):
    """The filtered, sorted card queryset (never a card waiting for erasure) plus what the filters were."""
    g = request.GET
    qs = AppCard.objects.live().select_related("user")
    owner = None
    if g.get("user"):
        try:
            owner = AppUser.objects.filter(pk=g["user"]).first()
        except ValidationError:  # not a UUID
            owner = None
        qs = qs.filter(user=owner) if owner else qs.none()
    exhibition = (g.get("exhibition") or "").strip()[:255]
    if exhibition:
        qs = qs.filter(exhibition_name=exhibition)
    if g.get("multi") == "1":
        qs = qs.filter(scan_count__gt=1)
    if _is_date(g.get("from", "")):
        qs = qs.filter(updated_at__date__gte=g["from"])
    if _is_date(g.get("to", "")):
        qs = qs.filter(updated_at__date__lte=g["to"])
    q = (g.get("q") or "").strip()[:100]
    if q:
        qs = qs.annotate(_p=Cast("phones", TextField()), _e=Cast("emails", TextField())).filter(
            Q(name__icontains=q) | Q(company__icontains=q) | Q(_e__icontains=q) | Q(_p__icontains=q))
    order, sort = _order(g.get("sort", ""))
    return qs.order_by(*order), owner, exhibition, q, sort


def _chips(request, owner, exhibition):
    """Active filters as removable chips: each carries the URL with that one filter taken off."""
    g = request.GET
    names = {"user": f"Owner: {_label(owner)}" if owner else "Owner: unknown", "exhibition": f"Exhibition: {exhibition}",
             "from": f"Changed from {g.get('from')}", "to": f"Changed to {g.get('to')}", "multi": "Scanned more than once", "q": f"Search: {g.get('q', '').strip()}"}
    chips = []
    for key, text in names.items():
        valid = _is_date(g.get(key, "")) if key in ("from", "to") else True
        if (g.get(key) or "").strip() and valid:
            rest = g.copy()
            rest.pop(key, None)
            rest.pop("page", None)
            chips.append({"label": text, "url": "?" + rest.urlencode()})
    return chips


def _stats():
    now = timezone.now()
    live = AppCard.objects.live().aggregate(total=Count("id"), week=Count("id", filter=Q(created_at__gte=now - timedelta(days=7))))
    return {**live, "users_on": AppUser.objects.filter(cloud_backup_enabled=True).exclude(status="deleted").count()}


class CardsView(CompanyAdminRequiredMixin, View):
    """Backed-up cards, by person (default) or all together."""

    def get(self, request):
        g = request.GET
        q = (g.get("q") or "").strip()[:100]
        ctx = {"f": g, "stats": _stats()}
        by_user = not any(g.get(k) for k in FILTERS) and g.get("view") != "cards"
        if by_user:
            live = Q(cards__deletion_requested_at__isnull=True)
            users = (AppUser.objects.annotate(n=Count("cards", filter=live), last=Max("cards__updated_at", filter=live))
                     .filter(n__gt=0).order_by("-last"))
            if q:
                users = users.filter(Q(email__icontains=q) | Q(name__icontains=q))
            _audit(request, "search" if q else "list", None, f"users q={q}" if q else "users")
            return render(request, "appauth/cards.html", {**ctx, "by_user": True, "page": _page(request, users)})

        qs, owner, exhibition, q, sort = _cards(request)
        _audit(request, "search" if q else "list", owner, urlencode({k: v for k, v in g.items() if k in (*FILTERS, "q") and v}))
        owners = (AppUser.objects.annotate(n=Count("cards", filter=Q(cards__deletion_requested_at__isnull=True)))
                  .filter(n__gt=0).order_by(Lower("email")).only("id", "email", "name")[:MAX_CHOICES])
        exhibitions = (AppCard.objects.live().exclude(exhibition_name="").order_by("exhibition_name")
                       .values_list("exhibition_name", flat=True).distinct()[:MAX_CHOICES])
        nxt = lambda col: ("-" + col if sort == col else col) if col != "updated" else ("updated" if sort == "-updated" else "-updated")  # noqa: E731
        keep = g.copy()
        for k in ("page", "sort"):
            keep.pop(k, None)
        return render(request, "appauth/cards.html", {
            **ctx, "owner": owner, "page": _page(request, qs), "chips": _chips(request, owner, exhibition), "sort": sort,
            "next": {c: nxt(c) for c in ("updated", "name", "company", "owner")},
            "owner_choices": [(str(u.pk), f"{_label(u)} · {u.email}" if u.name else u.email) for u in owners],
            "exhibition_choices": [(e, e) for e in exhibitions], "qs": keep.urlencode(),
            "export_qs": urlencode({k: v for k, v in g.items() if k in (*FILTERS, "q", "sort") and v}),
        })


class CardsExportView(CompanyAdminRequiredMixin, View):
    """CSV of the current filtered list. Logged like any other look at the cards."""

    def get(self, request):
        qs, owner, *_ = _cards(request)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="backed-up-cards.csv"'
        w = csv.writer(resp)
        w.writerow(["name", "company", "title", "phones", "emails", "owner_email"])
        rows = 0
        for c in qs.only("name", "company", "designation", "phones", "emails", "user__email").iterator():
            w.writerow([_safe_cell(x) for x in (c.name, c.company, c.designation, "; ".join(c.phones), "; ".join(c.emails),
                                                c.user.email if c.user else "")])
            rows += 1
        _audit(request, "export", owner, f"{rows} rows " + urlencode({k: v for k, v in request.GET.items() if k in (*FILTERS, "q") and v}))
        return resp


class CardDetailView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        card = get_object_or_404(AppCard.objects.live().select_related("user"), pk=pk)
        _audit(request, "detail", card.user, f"card={card.pk}")
        others = AppCard.objects.live().filter(user=card.user).exclude(pk=card.pk).count() if card.user else 0
        return render(request, "appauth/card_detail.html", {"c": card, "others": others})

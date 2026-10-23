import csv
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin
from apps.costing import service
from apps.costing.models import INPUT_FIELDS, Estimate

SCALARS = [f for f in INPUT_FIELDS if f not in ("people", "others")]
DEFAULTS = {"name": "", "client_name": "", "quote_date": None, "dedicated_days": "45", "client_days": "60", "rent_monthly": "", "ai_per_person_month": "",
            "margin_percent": "50", "margin_mode": "markup", "pitch_price": ""}


def _rows(raw):
    try:
        data = json.loads(raw or "[]")
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def read_inputs(post):
    """The estimate form as a dict of cleaned inputs. Numbers stay text until `service` uses them."""
    i = {f: (post.get(f) or "").strip() for f in SCALARS}
    try:
        i["quote_date"] = date.fromisoformat(i["quote_date"])
    except ValueError:
        i["quote_date"] = timezone.localdate()
    i["people"], i["others"] = service.clean_rows(_rows(post.get("people_json")), _rows(post.get("others_json")))
    return i


def compute(company, inputs):
    hpm, hpd = service.office_hours(company)
    return service.compute({**inputs, "hours_per_month": hpm, "hours_per_day": hpd})


class CostingAccessMixin(CompanyAdminRequiredMixin):
    """Owners and admins only. The salaries typed here are never shown to anyone else."""

    def estimate_or_404(self, pk):
        try:
            return Estimate.objects.get(pk=pk, company=self.request.company)
        except Estimate.DoesNotExist:
            raise Http404


def _figures(company, estimates):
    """One dict per estimate: the saved quote's cost, the price quoted, and the profit it leaves."""
    out = []
    for e in estimates:
        r = compute(company, e.inputs())
        price = r["pitch"] if r["has_pitch"] else r["price"]
        profit = price - r["total"]
        out.append({"e": e, "cost": r["total"], "price": price, "profit": profit,
                    "margin": (profit / price * 100) if price else Decimal("0"), "search": f"{e.name} {e.client_name}".lower()})
    return out


class EstimateListView(CostingAccessMixin, View):
    """The saved estimates with a report over them: totals, by client, by month."""

    def get(self, request):
        every = Estimate.objects.filter(company=request.company)
        months = [f"{d:%Y-%m}" for d in every.dates("quote_date", "month", order="DESC")]
        month = request.GET.get("month", "all")
        qs = every.filter(quote_date__year=month[:4], quote_date__month=month[5:7]) if month in months else every
        month = month if month in months else "all"
        rows = _figures(request.company, qs)
        cost, price = sum((r["cost"] for r in rows), Decimal("0")), sum((r["price"] for r in rows), Decimal("0"))
        by_client = {}
        for r in rows:
            c = by_client.setdefault(r["e"].client_name or "No client", {"n": 0, "cost": Decimal("0"), "price": Decimal("0")})
            c["n"] += 1
            c["cost"] += r["cost"]
            c["price"] += r["price"]
        return render(request, "costing/list.html", {
            "rows": rows, "has_any": every.exists(), "month": month,
            "months": [{"value": m, "label": date(int(m[:4]), int(m[5:]), 1).strftime("%b %Y")} for m in months],
            "stats": {"n": len(rows), "cost": cost, "price": price, "profit": price - cost,
                      "margin": ((price - cost) / price * 100) if price else Decimal("0")},
            "by_client": sorted(({"name": k, **v, "profit": v["price"] - v["cost"]} for k, v in by_client.items()),
                                key=lambda c: -c["price"]),
        })


def _csv_safe(text):
    """A spreadsheet runs a cell that starts with = + - @ as a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


class EstimateExportView(CostingAccessMixin, View):
    def get(self, request):
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="project-costing.csv"'
        w = csv.writer(resp)
        w.writerow(["Quote date", "Project", "Client", "Our cost (INR)", "Price (INR)", "Profit (INR)", "Margin on price %"])
        for r in _figures(request.company, Estimate.objects.filter(company=request.company)):
            e = r["e"]
            w.writerow([e.quote_date.isoformat(), _csv_safe(e.name), _csv_safe(e.client_name), r["cost"], r["price"],
                        r["profit"], f"{r['margin']:.1f}"])
        return resp


class EstimateFormView(CostingAccessMixin, View):
    def get(self, request, pk=None):
        e = self.estimate_or_404(pk) if pk else None
        data = e.inputs() if e else {**DEFAULTS, "quote_date": timezone.localdate(), "people": [], "others": []}
        return self.page(request, e, data)

    def post(self, request, pk=None):
        e = self.estimate_or_404(pk) if pk else Estimate(company=request.company, created_by=request.user)
        data = read_inputs(request.POST)
        if not data["name"]:
            messages.error(request, "Give the estimate a project name.")
            return self.page(request, e if pk else None, data)
        for f in INPUT_FIELDS:
            setattr(e, f, data[f])
        e.save()
        messages.success(request, f"Saved {e.name}.")
        return redirect("costing:estimate_detail", pk=e.pk)

    def page(self, request, e, data):
        return render(request, "costing/form.html", {
            "e": e, "d": data, "r": compute(request.company, data),
            "people_json": json.dumps(data["people"]), "others_json": json.dumps(data["others"]),
        })


class EstimateDetailView(CostingAccessMixin, View):
    """Read-only page that walks through every number: where it comes from and how it adds up."""

    def get(self, request, pk):
        e = self.estimate_or_404(pk)
        d = e.inputs()
        return render(request, "costing/detail.html", {"e": e, "d": d, "r": compute(request.company, d)})


class EstimateCalcView(CostingAccessMixin, View):
    """The live result panel: htmx posts the form here on every change, nothing is saved."""

    def post(self, request):
        return render(request, "costing/_result.html", {"r": compute(request.company, read_inputs(request.POST)), "oob": True})


class EstimateDeleteView(CostingAccessMixin, View):
    def post(self, request, pk):
        e = self.estimate_or_404(pk)
        name = e.name
        e.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("costing:estimate_list")


class EstimateDuplicateView(CostingAccessMixin, View):
    def post(self, request, pk):
        e = self.estimate_or_404(pk)
        e.pk, e.id = None, None
        e.name = f"{e.name} (copy)"[:200]
        e.created_by = request.user
        e.save()
        messages.success(request, "Estimate duplicated.")
        return redirect("costing:estimate_edit", pk=e.pk)


class EstimateQuoteView(CostingAccessMixin, View):
    """Client-safe page: line prices and a total. No salaries, costs, rates or margin."""

    def get(self, request, pk):
        e = self.estimate_or_404(pk)
        lines, price = service.quote_lines(compute(request.company, e.inputs()))
        return render(request, "costing/quote.html", {"e": e, "lines": lines, "price": price})

"""Staff page: which parts of card scanning people have to fix. Reads ScanFeedback only (no people, no card text)."""
import csv

from django.db.models import Avg, Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from apps.appauth.models import ScanFeedback
from apps.appauth.web import _is_date, _safe_cell
from apps.core.mixins import CompanyAdminRequiredMixin

FIELDS = ScanFeedback.FIELD_KEYS
STATUSES = ScanFeedback.STATUSES
LABELS = {"name": "Name", "company": "Company", "designation": "Job title", "phones": "Phones", "emails": "Emails",
          "website": "Website", "address": "Address"}
MAX_VERSIONS = 100


def _filtered(request):
    """Scans in the chosen range. The version is applied separately, because compare needs two of them."""
    g = request.GET
    qs = ScanFeedback.objects.all()
    if _is_date(g.get("from", "")):
        qs = qs.filter(received_at__date__gte=g["from"])
    if _is_date(g.get("to", "")):
        qs = qs.filter(received_at__date__lte=g["to"])
    if g.get("mode") in ScanFeedback.MODES:
        qs = qs.filter(scan_mode=g["mode"])
    if g.get("parser") in ScanFeedback.PARSERS:
        qs = qs.filter(parser=g["parser"])
    return qs


def field_rows(qs):
    """One aggregate query -> a row per field: scans, each status, fix rate (%) and average confidence."""
    agg = {"_scans": Count("id")}
    for f in FIELDS:
        agg[f"{f}__n"] = Count("id", filter=~Q(**{f"{f}_status": ""}))
        for st in STATUSES:
            agg[f"{f}__{st}"] = Count("id", filter=Q(**{f"{f}_status": st}))
        agg[f"{f}__conf"] = Avg(f"{f}_conf")
    r = qs.aggregate(**agg)
    rows = []
    for f in FIELDS:
        n = r[f"{f}__n"]
        fixes = sum(r[f"{f}__{st}"] for st in STATUSES[1:])
        rows.append({"field": f, "label": LABELS[f], "scans": n, **{st: r[f"{f}__{st}"] for st in STATUSES},
                     "fixes": fixes, "fix_rate": round(100 * fixes / n, 1) if n else None, "conf": r[f"{f}__conf"]})
    rows.sort(key=lambda x: (x["fix_rate"] is None, -(x["fix_rate"] or 0), x["field"]))  # worst first, unreported last
    return rows, r["_scans"]


def overall_fix_rate(rows):
    n, fixes = sum(x["scans"] for x in rows), sum(x["fixes"] for x in rows)
    return round(100 * fixes / n, 1) if n else None


def compare_rows(a_rows, b_rows):
    """Side by side per field. `change` is B minus A in percentage points; lower is better."""
    b_by = {x["field"]: x for x in b_rows}
    out = []
    for a in a_rows:
        b = b_by[a["field"]]
        change = round(b["fix_rate"] - a["fix_rate"], 1) if a["fix_rate"] is not None and b["fix_rate"] is not None else None
        out.append({"label": a["label"], "a": a, "b": b, "change": change,
                    "tone": "" if not change else ("good" if change < 0 else "bad")})
    out.sort(key=lambda x: (x["change"] is None, -(x["change"] or 0)))  # biggest regression first
    return out


def _versions():
    return list(ScanFeedback.objects.values("app_version").annotate(last=Max("received_at"), n=Count("id"))
                .order_by("-last")[:MAX_VERSIONS])


class ScanQualityView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        g = request.GET
        versions = _versions()
        known = {v["app_version"] for v in versions}
        base = _filtered(request)
        ctx = {"f": g, "version_choices": [(v["app_version"], f"{v['app_version']} · {v['n']} scans") for v in versions],
               "has_any": ScanFeedback.objects.exists()}
        if g.get("view") == "compare":
            a, b = (g.get("a") if g.get("a") in known else ""), (g.get("b") if g.get("b") in known else "")
            ctx.update(compare=True, a=a, b=b)
            if a and b:
                ra, na = field_rows(base.filter(app_version=a))
                rb, nb = field_rows(base.filter(app_version=b))
                ctx.update(rows=compare_rows(ra, rb), a_scans=na, b_scans=nb, a_rate=overall_fix_rate(ra), b_rate=overall_fix_rate(rb))
            return render(request, "appauth/scan_quality.html", ctx)
        version = g.get("version") if g.get("version") in known else ""
        qs = base.filter(app_version=version) if version else base
        rows, scans = field_rows(qs)
        per_version = list(base.values("app_version").annotate(n=Count("id")).order_by("-n")[:5])
        keep = g.copy()
        keep.pop("page", None)
        ctx.update(rows=rows, scans=scans, rate=overall_fix_rate(rows), per_version=per_version, version=version,
                   export_qs=keep.urlencode())
        return render(request, "appauth/scan_quality.html", ctx)


class ScanQualityExportView(CompanyAdminRequiredMixin, View):
    """CSV of what the page shows: one row per field, for the chosen version, or for each of the two compared."""

    def get(self, request):
        g = request.GET
        known = {v["app_version"] for v in _versions()}
        base = _filtered(request)
        if g.get("view") == "compare":
            groups = [(v, base.filter(app_version=v)) for v in (g.get("a"), g.get("b")) if v in known]
        else:
            v = g.get("version") if g.get("version") in known else ""
            groups = [(v or "all", base.filter(app_version=v) if v else base)]
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="scan-quality.csv"'
        w = csv.writer(resp)
        w.writerow(["field", "app_version", "scans", "ok", "edited", "added", "removed", "fixed_format", "fix_rate", "avg_confidence"])
        for version, qs in groups:
            for x in field_rows(qs)[0]:
                w.writerow([x["field"], _safe_cell(version), x["scans"], x["ok"], x["edited"], x["added"], x["removed"], x["fixed_format"],
                            "" if x["fix_rate"] is None else x["fix_rate"], "" if x["conf"] is None else round(x["conf"], 3)])
        return resp

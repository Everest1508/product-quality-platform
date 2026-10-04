"""Numbers behind the error sparklines, flags and the detail chart.

One query per page of groups, not one per row. Days are in the site time zone,
the same one the rest of the app reports in.
"""

from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.ingestion.models import ErrorOccurrence

LIST_DAYS = 14
DETAIL_DAYS = 30
SPARK_W, SPARK_H = 64, 20


def _days(count):
    today = timezone.localdate()
    return [today - timedelta(days=count - 1 - i) for i in range(count)]


def _daily_counts(group_ids, days):
    since = timezone.make_aware(datetime.combine(days[0], time.min))
    rows = (
        ErrorOccurrence.objects.filter(error_group_id__in=group_ids, created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("error_group_id", "day")
        .annotate(n=Count("id"))
    )
    out = {}
    for row in rows:
        out.setdefault(row["error_group_id"], {})[row["day"]] = row["n"]
    return out


def sparkline(counts):
    """Plain data for a tiny inline chart: a polyline, a filled area, and totals."""
    peak = max(counts) if counts else 0
    n = max(1, len(counts) - 1)
    pts = []
    for i, c in enumerate(counts):
        x = round(i * SPARK_W / n, 1)
        y = round(SPARK_H - 2 - (c / peak) * (SPARK_H - 4), 1) if peak else SPARK_H - 2
        pts.append((x, y))
    line = " ".join(f"{x},{y}" for x, y in pts)
    area = f"0,{SPARK_H} {line} {SPARK_W},{SPARK_H}"
    recent, before = sum(counts[-3:]), sum(counts[-6:-3])
    return {
        "counts": counts,
        "total": sum(counts),
        "peak": peak,
        "line": line,
        "area": area,
        "width": SPARK_W,
        "height": SPARK_H,
        # Three days against the three before, so one noisy day does not flip it.
        "rising": recent > 0 and recent >= max(2, before * 1.5),
    }


def attach_trends(groups, days=LIST_DAYS):
    """Put `.trend`, `.is_regression`, `.new_in_release` and `.first_version_label`
    on each group and return them as a list."""
    from apps.products.models import ProductVersion

    groups = list(groups)
    if not groups:
        return groups
    day_list = _days(days)
    daily = _daily_counts([g.pk for g in groups], day_list)
    current = {
        v.product_id: v.pk
        for v in ProductVersion.objects.filter(
            product_id__in={g.product_id for g in groups}, is_current=True
        )
    }
    first_ids = {g.first_version_id for g in groups if g.first_version_id}
    labels = dict(ProductVersion.objects.filter(pk__in=first_ids).values_list("pk", "version_string"))
    for g in groups:
        per_day = daily.get(g.pk, {})
        g.trend = sparkline([per_day.get(d, 0) for d in day_list])
        g.is_regression = g.regression_count > 0 and g.status in ("open", "investigating")
        g.new_in_release = bool(g.first_version_id and current.get(g.product_id) == g.first_version_id)
        g.first_version_label = labels.get(g.first_version_id, "")
    return groups


def detail_trend(group, days=DETAIL_DAYS):
    """Daily bars and a per-release breakdown for one group's detail page."""
    day_list = _days(days)
    per_day = _daily_counts([group.pk], day_list).get(group.pk, {})
    counts = [per_day.get(d, 0) for d in day_list]
    peak = max(counts) if counts else 0
    bars = [
        {"date": d, "count": c, "pct": round(c / peak * 100) if peak else 0}
        for d, c in zip(day_list, counts)
    ]
    since = timezone.make_aware(datetime.combine(day_list[0], time.min))
    by_version = list(
        ErrorOccurrence.objects.filter(error_group=group, created_at__gte=since)
        .values("version__version_string")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    by_version = [
        {"version": row["version__version_string"] or "Unknown", "count": row["n"]} for row in by_version
    ]
    return {"bars": bars, "total": sum(counts), "peak": peak, "days": days, "by_version": by_version}

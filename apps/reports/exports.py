"""Turn a report Result into a file. The file name says what it is: Company_Report-name_period.xlsx."""

import io
import re
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone

from apps.core.csvx import csv_response

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def file_stem(report, ctx):
    when = f"as-of-{ctx.today:%Y-%m-%d}" if report.snapshot else f"{ctx.start:%Y-%m-%d}_to_{ctx.end:%Y-%m-%d}"
    return f"{_slug(ctx.company.name)}_{_slug(report.title)}_{when}"


def _cell(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime) and timezone.is_aware(v):
        return timezone.localtime(v).replace(tzinfo=None)
    return v


def _plain(v):
    v = _cell(v)
    if v is None:
        return ""
    if isinstance(v, datetime):
        return f"{v:%d %b %Y %H:%M}"
    if isinstance(v, date):
        return f"{v:%d %b %Y}"
    return v


def csv_file(report, ctx, result):
    return csv_response(file_stem(report, ctx) + ".csv", result.columns, [[_plain(c) for c in r] for r in result.rows])


def xlsx_file(report, ctx, result):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = re.sub(r"[\[\]:*?/\\]", "", report.title)[:31]
    ws.append(result.columns)
    head = PatternFill("solid", fgColor="2563EB")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head
        c.alignment = Alignment(vertical="center", wrap_text=True)
    widths = [len(str(h)) for h in result.columns]
    for row in result.rows:
        vals = [_cell(v) for v in row]
        ws.append(vals)
        for i, v in enumerate(vals):
            widths[i] = max(widths[i], len(f"{v:%d %b %Y}") if isinstance(v, (date, datetime)) else len(str(v if v is not None else "")))
    for r in ws.iter_rows(min_row=2):
        for c in r:
            if isinstance(c.value, datetime):
                c.number_format = "DD MMM YYYY h:mm AM/PM"
            elif isinstance(c.value, date):
                c.number_format = "DD MMM YYYY"
            elif isinstance(c.value, float):
                c.number_format = "#,##0.00"
            elif isinstance(c.value, int):
                c.number_format = "#,##0"
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = min(max(w + 2, 10), 60)
    ws.freeze_panes = "A2"
    if result.rows:
        ws.auto_filter.ref = ws.dimensions

    about = wb.create_sheet("About")
    period = f"As of {ctx.today:%d %b %Y}" if report.snapshot else f"{ctx.start:%d %b %Y} to {ctx.end:%d %b %Y}"
    lines = [
        ("Report", report.title),
        ("What it answers", report.blurb),
        ("Company", ctx.company.name),
        ("Period", period),
        ("Project", ctx.product.name if ctx.product else "All projects you can see"),
        ("Person", (ctx.person.get_full_name() or ctx.person.username) if ctx.person else "Everyone"),
        ("Rows", len(result.rows)),
        ("Prepared by", ctx.user.get_full_name() or ctx.user.username),
        ("Prepared on", f"{timezone.localtime():%d %b %Y, %I:%M %p}"),
    ] + [(k, v) for k, v in result.kpis] + ([("Note", result.note)] if result.note else [])
    for k, v in lines:
        about.append([k, v])
    for c in about["A"]:
        c.font = Font(bold=True)
    about.column_dimensions["A"].width = 20
    about.column_dimensions["B"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(), content_type=XLSX)
    resp["Content-Disposition"] = f'attachment; filename="{file_stem(report, ctx)}.xlsx"'
    return resp

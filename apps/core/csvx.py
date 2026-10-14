import csv

from django.http import HttpResponse


def _safe(v):
    """A spreadsheet runs a cell that starts with = + - @ as a formula; a leading quote keeps it text."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def csv_response(filename, header, rows):
    r = HttpResponse(content_type="text/csv; charset=utf-8")
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    r.write("﻿")  # Excel reads UTF-8 only with a byte-order mark
    w = csv.writer(r)
    w.writerow(header)
    for row in rows:
        w.writerow([_safe(c) for c in row])
    return r

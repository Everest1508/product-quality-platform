"""Reading and repairing Decimal columns that SQLite can no longer convert.

SQLite has no real DECIMAL type. A `DecimalField` column is declared with NUMERIC
affinity, so a value written as a decimal string comes back as a float and Django
re-runs it through `Context(prec=15).create_decimal_from_float(...).quantize(...)`
in `django/db/backends/sqlite3/operations.py::get_decimalfield_converter`.

That conversion raises `decimal.InvalidOperation` for a value it cannot quantize
to the field's `decimal_places` -- a non-finite value (`inf`, `-inf`, `NaN`) or a
magnitude with more digits than the default 28-digit context allows. One such row
is enough to 500 *every* page that reads the table, because the failure happens
while the cursor is being built, before any of the view's own logic runs:

    InvalidOperation at /dashboards/
    .../django/db/backends/sqlite3/operations.py, line 334, in converter
    Raised during: apps.dashboards.views.DashboardView

The row cannot be repaired through the ORM -- `Model.objects.get(pk=...)` runs the
same converter and raises before returning -- so both the audit and the repair
here go through raw SQL and write with `QuerySet.update()`, which never reads the
row back.
"""

import decimal
import json
from decimal import Decimal, InvalidOperation

from django.db import connections

# Mirrors the context Django builds in `get_decimalfield_converter`.
PRECISION = 15
_CONTEXT = decimal.Context(prec=PRECISION)


def _create_decimal(raw):
    """The value Django hands to `create_decimal_from_float`, or raise.

    NUMERIC affinity means a well-formed decimal string comes back as float (or
    int for a whole number), which is why the float entry point is correct. A
    string arriving here means the column holds text that is not a number, and
    `create_decimal_from_float` refuses it outright.
    """
    if isinstance(raw, bytes):
        raw = raw.decode()
    if isinstance(raw, (int, float)):
        return _CONTEXT.create_decimal_from_float(raw)
    raise TypeError(
        f"argument must be int or float (got {type(raw).__name__}: {raw!r})"
    )


def decimal_read_error(raw, decimal_places):
    """Why Django cannot read `raw` as a DecimalField with `decimal_places`.

    Returns None when the conversion succeeds, otherwise a short reason string.
    This is the same two steps the backend converter performs, in the same order.
    """
    try:
        value = _create_decimal(raw)
    except (TypeError, ValueError, ArithmeticError, InvalidOperation) as exc:
        return f"not a number: {exc}"
    if not value.is_finite():
        return f"non-finite value: {value}"
    try:
        value.quantize(Decimal(1).scaleb(-decimal_places))
    except (InvalidOperation, ValueError, ArithmeticError) as exc:
        return f"cannot quantize to {decimal_places}dp: {value} ({exc})"
    return None


def iter_decimal_fields(apps=None):
    """(model, field) for every concrete DecimalField, table order."""
    from django.apps import apps as django_apps
    from django.db import models

    registry = apps or django_apps
    for model in registry.get_models():
        if model._meta.proxy or model._meta.abstract:
            continue
        for field in model._meta.concrete_fields:
            if isinstance(field, models.DecimalField):
                yield model, field


def scan(using="default", model_label=None):
    """Every unreadable decimal cell, newest-looking fields first.

    Returns a list of dicts: table, column, model, pk, raw, reason. Read with
    raw SQL on purpose -- the ORM cannot load a row whose decimal column is the
    thing that is broken.
    """
    connection = connections[using]
    qn = connection.ops.quote_name
    problems = []
    for model, field in iter_decimal_fields():
        if model_label and model_label not in f"{model._meta.app_label}.{model.__name__}":
            continue
        table = model._meta.db_table
        pk = model._meta.pk.column
        sql = (
            f"SELECT {qn(pk)}, {qn(field.column)} FROM {qn(table)} "
            f"WHERE {qn(field.column)} IS NOT NULL"
        )
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        for row_pk, raw in rows:
            reason = decimal_read_error(raw, field.decimal_places)
            if reason:
                problems.append(
                    {
                        "model": f"{model._meta.app_label}.{model.__name__}",
                        "table": table,
                        "column": field.column,
                        "pk": row_pk,
                        "raw": repr(raw),
                        "reason": reason,
                    }
                )
    return problems


def repair(problems, using="default", replacement=Decimal("0")):
    """Write `replacement` into every listed cell and return what changed.

    `QuerySet.update()` is a write-only path, so this works even though reading
    the row is what raises. One UPDATE per cell: there are never enough of these
    to be worth batching, and a per-row statement names the offending pk in the
    log if a repair needs undoing.
    """
    connection = connections[using]
    changed = []
    for problem in problems:
        model = _resolve_model(problem["model"])
        model._default_manager.using(using).filter(pk=problem["pk"]).update(
            **{problem["column"]: replacement}
        )
        changed.append(problem)
    return changed


def _resolve_model(label):
    from django.apps import apps as django_apps

    return django_apps.get_model(label)


def dump_backup(problems, path):
    """Write the raw values to JSON so a repair is reversible."""
    with open(path, "w") as handle:
        json.dump(problems, handle, indent=2)
    return path

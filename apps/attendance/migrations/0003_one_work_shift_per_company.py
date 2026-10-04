from django.db import migrations, models


def drop_duplicate_shifts(apps, schema_editor):
    """Keep the oldest shift per company. `shift_for` used to create a row on
    first read with no uniqueness, so a concurrent first load could leave two."""
    WorkShift = apps.get_model("attendance", "WorkShift")
    seen = set()
    for shift in WorkShift.objects.order_by("company_id", "id"):
        if shift.company_id in seen:
            shift.delete()
        else:
            seen.add(shift.company_id)


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_workshift"),
    ]

    operations = [
        migrations.RunPython(drop_duplicate_shifts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="workshift",
            constraint=models.UniqueConstraint(fields=("company",), name="one_work_shift_per_company"),
        ),
    ]

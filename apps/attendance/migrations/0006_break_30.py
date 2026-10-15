from django.db import migrations, models


def to_30(apps, schema_editor):
    apps.get_model("attendance", "WorkShift").objects.filter(break_minutes=60).update(break_minutes=30)


class Migration(migrations.Migration):
    dependencies = [("attendance", "0005_shift_end_1830")]
    operations = [
        migrations.AlterField(
            model_name="workshift",
            name="break_minutes",
            field=models.PositiveIntegerField(
                default=30, help_text="Unpaid scheduled break, deducted from hours worked."
            ),
        ),
        migrations.RunPython(to_30, migrations.RunPython.noop),
    ]

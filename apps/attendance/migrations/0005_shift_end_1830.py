import datetime

from django.db import migrations, models


def move_end(apps, schema_editor):
    # Only rows still on the old default; a customised end time is left alone.
    apps.get_model("attendance", "WorkShift").objects.filter(
        end_time=datetime.time(19, 0)
    ).update(end_time=datetime.time(18, 30))


class Migration(migrations.Migration):
    dependencies = [("attendance", "0004_attendance_correction")]

    operations = [
        migrations.AlterField(
            model_name="workshift",
            name="end_time",
            field=models.TimeField(default=datetime.time(18, 30)),
        ),
        migrations.RunPython(move_end, migrations.RunPython.noop),
    ]

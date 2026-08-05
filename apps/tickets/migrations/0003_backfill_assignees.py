from django.db import migrations


def backfill_assignees(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    for ticket in Ticket.objects.filter(assigned_to__isnull=False):
        ticket.assignees.set([ticket.assigned_to_id])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0002_ticket_assignees_ticket_deadline"),
    ]

    operations = [
        migrations.RunPython(backfill_assignees, noop),
    ]

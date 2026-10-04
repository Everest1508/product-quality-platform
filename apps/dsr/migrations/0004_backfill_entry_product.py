from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill(apps, schema_editor):
    """Entries written from a ticket get that ticket's product."""
    DSREntry = apps.get_model("dsr", "DSREntry")
    Ticket = apps.get_model("tickets", "Ticket")
    DSREntry.objects.filter(ticket__isnull=False, product__isnull=True).update(
        product_id=Subquery(Ticket.objects.filter(pk=OuterRef("ticket_id")).values("product_id")[:1])
    )


class Migration(migrations.Migration):
    dependencies = [
        ("dsr", "0003_dsrentry_product"),
        ("tickets", "0007_backfill_ticket_keys"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]

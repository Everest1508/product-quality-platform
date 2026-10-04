from django.db import migrations

from apps.products.keys import unique_key


def backfill(apps, schema_editor):
    """Give every product a key and number its tickets 1, 2, 3 in creation order."""
    Product = apps.get_model("products", "Product")
    Ticket = apps.get_model("tickets", "Ticket")

    taken_by_company = {}
    for product in Product.objects.order_by("company_id", "created_at", "pk"):
        taken = taken_by_company.setdefault(product.company_id, set())
        if not product.key:
            product.key = unique_key(product.name, taken)
        taken.add(product.key)

        count = 0
        for ticket in Ticket.objects.filter(product_id=product.pk).order_by("created_at", "pk"):
            count += 1
            Ticket.objects.filter(pk=ticket.pk).update(number=count)
        product.ticket_counter = count
        product.save(update_fields=["key", "ticket_counter"])


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0006_ticket_keys"),
        ("products", "0006_ticket_keys"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]

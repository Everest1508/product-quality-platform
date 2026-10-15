from django.db import migrations, models

OLD = {"food": "Food & drinks", "travel": "Travel", "office": "Office", "software": "Software"}


def keep_old(apps, schema_editor):
    Expense = apps.get_model("expenses", "Expense")
    for key, label in OLD.items():
        Expense.objects.filter(category=key).update(category="other", category_other=label)


class Migration(migrations.Migration):
    dependencies = [("expenses", "0002_remove_expense_settled_at_remove_expense_split_with")]
    operations = [
        migrations.AddField(
            model_name="expense", name="category_other", field=models.CharField(blank=True, max_length=60)
        ),
        migrations.RunPython(keep_old, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="expense",
            name="category",
            field=models.CharField(
                choices=[("tea", "Tea"), ("ai", "AI subscription"), ("server", "Server rent"),
                         ("trip", "Team trip"), ("other", "Other")],
                default="other", max_length=12,
            ),
        ),
    ]

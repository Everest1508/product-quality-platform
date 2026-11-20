from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("costing", "0002_alter_estimate_options_estimate_quote_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimate",
            name="actual_price",
            field=models.CharField(blank=True, help_text="The price we actually got the project for.", max_length=20),
        ),
    ]

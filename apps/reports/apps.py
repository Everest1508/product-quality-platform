from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = "apps.reports"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import audit, finance, insights, money, people, work, workforce  # noqa: F401  (importing registers the reports)

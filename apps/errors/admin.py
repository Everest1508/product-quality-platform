from django.contrib import admin

from apps.ingestion.models import ErrorGroup, ErrorOccurrence


@admin.register(ErrorGroup)
class ErrorGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "product", "severity", "status", "occurrence_count", "last_seen")
    list_filter = ("severity", "status", "product__company")
    search_fields = ("title", "fingerprint")
    readonly_fields = ("fingerprint", "first_seen", "last_seen")


@admin.register(ErrorOccurrence)
class ErrorOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("error_group", "environment", "user_ref", "created_at")
    list_filter = ("environment",)
    readonly_fields = ("created_at",)

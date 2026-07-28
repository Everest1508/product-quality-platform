from django.contrib import admin

from apps.dashboards.models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "title", "actor", "company", "created_at")
    list_filter = ("event_type",)

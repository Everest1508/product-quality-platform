from django.contrib import admin

from apps.automation.models import AutoTicketLog, AutoTicketRule


@admin.register(AutoTicketRule)
class AutoTicketRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "trigger_type", "threshold_count", "window_minutes", "action", "is_active", "last_triggered_at")
    list_filter = ("trigger_type", "action", "is_active")
    search_fields = ("name",)


@admin.register(AutoTicketLog)
class AutoTicketLogAdmin(admin.ModelAdmin):
    list_display = ("rule", "matched_count", "action_taken", "ticket", "created_at")
    list_filter = ("action_taken",)
    raw_id_fields = ("rule", "error_group", "ticket")

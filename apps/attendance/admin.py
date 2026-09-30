from django.contrib import admin

from apps.attendance.models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "date", "check_in", "check_out", "worked_hours", "is_edited")
    list_filter = ("company", "date", "is_edited")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    date_hierarchy = "date"
    ordering = ("-date", "user__username")

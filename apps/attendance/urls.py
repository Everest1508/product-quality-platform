from datetime import date

from django.urls import path, register_converter

from apps.attendance import views


class IsoDate:
    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value):
        return date.fromisoformat(value)  # a bad date like 2026-02-31 raises ValueError, so 404

    def to_url(self, value):
        return str(value)


register_converter(IsoDate, "date")

app_name = "attendance"

urlpatterns = [
    path("", views.MyAttendanceView.as_view(), name="my_attendance"),
    path("punch/", views.AttendancePunchView.as_view(), name="punch"),
    path("team/", views.TeamAttendanceView.as_view(), name="team_attendance"),
    path("weekly-off/", views.WeeklyOffView.as_view(), name="weekly_off"),
    path("timesheet/", views.TimesheetView.as_view(), name="timesheet"),
    path("timesheet/<int:user_id>/", views.TimesheetDetailView.as_view(), name="timesheet_detail"),
    path("corrections/", views.CorrectionQueueView.as_view(), name="corrections"),
    path("corrections/request/", views.CorrectionRequestView.as_view(), name="correction_request"),
    path("corrections/<int:pk>/cancel/", views.CorrectionCancelView.as_view(), name="correction_cancel"),
    path("corrections/<int:pk>/<str:action>/", views.CorrectionDecisionView.as_view(), name="correction_decision"),
    path("add/<int:user_id>/<date:day>/", views.AttendanceAddView.as_view(), name="attendance_add"),
    path("<int:pk>/edit/", views.AttendanceEditView.as_view(), name="attendance_edit"),
]

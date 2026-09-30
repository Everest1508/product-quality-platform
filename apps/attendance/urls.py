from django.urls import path

from apps.attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.MyAttendanceView.as_view(), name="my_attendance"),
    path("punch/", views.AttendancePunchView.as_view(), name="punch"),
    path("team/", views.TeamAttendanceView.as_view(), name="team_attendance"),
    path("timesheet/", views.TimesheetView.as_view(), name="timesheet"),
    path("timesheet/<int:user_id>/", views.TimesheetDetailView.as_view(), name="timesheet_detail"),
    path("<int:pk>/edit/", views.AttendanceEditView.as_view(), name="attendance_edit"),
]

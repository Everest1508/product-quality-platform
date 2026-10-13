from django.urls import path

from apps.attendance import views

app_name = "attendance"

urlpatterns = [
    path("", views.AttendanceShellView.as_view(), name="my_attendance"),
    path("team/", views.AttendanceAdminShellView.as_view(), name="team_attendance"),
    path("timesheet/", views.AttendanceAdminShellView.as_view(), name="timesheet"),
    path("timesheet/<int:user_id>/", views.AttendanceAdminShellView.as_view(), name="timesheet_detail"),
    path("corrections/", views.AttendanceAdminShellView.as_view(), name="corrections"),
    path("corrections/request/", views.AttendanceShellView.as_view(), name="correction_request"),
    path("<int:pk>/edit/", views.AttendanceEditView.as_view(), name="attendance_edit"),
]

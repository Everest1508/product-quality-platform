from django.urls import path

from apps.leave import views

app_name = "leave"

urlpatterns = [
    path("", views.LeaveShellView.as_view(), name="my_leave"),
    path("apply/", views.LeaveShellView.as_view(), name="apply"),
    path("calendar/", views.LeaveShellView.as_view(), name="calendar"),
    path("approvals/", views.LeaveApproverShellView.as_view(), name="approvals"),
    path("policies/", views.LeavePolicyShellView.as_view(), name="policies"),
]

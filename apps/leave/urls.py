from django.urls import path

from apps.leave import views

app_name = "leave"

urlpatterns = [
    path("", views.MyLeaveView.as_view(), name="my_leave"),
    path("apply/", views.LeaveApplyView.as_view(), name="apply"),
    path(
        "apply/preview/",
        views.LeaveSplitPreviewView.as_view(),
        name="split_preview",
    ),
    path("<int:pk>/cancel/", views.LeaveCancelView.as_view(), name="cancel"),
    path("approvals/", views.LeaveQueueView.as_view(), name="approvals"),
    path(
        "<int:pk>/<str:action>/",
        views.LeaveDecisionView.as_view(),
        name="decision",
    ),
    path("policies/", views.LeavePolicyListView.as_view(), name="policies"),
    path("policies/add/", views.LeavePolicyCreateView.as_view(), name="policy_add"),
    path(
        "policies/<int:pk>/",
        views.LeavePolicyUpdateView.as_view(),
        name="policy_update",
    ),
]
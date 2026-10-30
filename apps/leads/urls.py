from django.urls import path

from apps.leads import views

app_name = "leads"

urlpatterns = [
    path("", views.LeadListView.as_view(), name="lead_list"),
    path("<int:pk>/", views.LeadDetailView.as_view(), name="lead_detail"),
    path("<int:pk>/log/", views.LeadLogView.as_view(), name="lead_log"),
    path("<int:pk>/status/", views.LeadStatusView.as_view(), name="lead_status"),
    path("<int:pk>/convert/", views.LeadConvertView.as_view(), name="lead_convert"),
    path("rotate/", views.LeadWebhookRotateView.as_view(), name="webhook_rotate"),
]

from django.urls import path

from apps.leads import views

app_name = "leads"

urlpatterns = [
    path("", views.LeadListView.as_view(), name="lead_list"),
    path("rotate/", views.LeadWebhookRotateView.as_view(), name="webhook_rotate"),
]

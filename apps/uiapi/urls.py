from django.urls import path

from apps.uiapi import tickets, views

app_name = "uiapi"

urlpatterns = [
    path("tickets/", tickets.TicketListAPIView.as_view(), name="tickets"),
    path("tickets/meta/", tickets.TicketMetaAPIView.as_view(), name="ticket_meta"),
    path("company/switch/", views.CompanySwitchAPIView.as_view(), name="company_switch"),
    path("bootstrap/", views.BootstrapView.as_view(), name="bootstrap"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", views.NotificationReadAllView.as_view(), name="notifications_read_all"),
]

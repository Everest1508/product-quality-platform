from django.urls import path

from apps.uiapi import products, tickets, views

app_name = "uiapi"

urlpatterns = [
    path("products/<int:pk>/nav/", products.ProductNavAPIView.as_view(), name="product_nav"),
    path("tickets/", tickets.TicketListAPIView.as_view(), name="tickets"),
    path("tickets/meta/", tickets.TicketMetaAPIView.as_view(), name="ticket_meta"),
    path("tickets/bulk-delete/", tickets.TicketBulkDeleteAPIView.as_view(), name="ticket_bulk_delete"),
    path("tickets/<int:pk>/status/", tickets.TicketStatusAPIView.as_view(), name="ticket_status"),
    path("tickets/<int:pk>/", tickets.TicketDetailAPIView.as_view(), name="ticket_detail"),
    path("company/switch/", views.CompanySwitchAPIView.as_view(), name="company_switch"),
    path("bootstrap/", views.BootstrapView.as_view(), name="bootstrap"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", views.NotificationReadAllView.as_view(), name="notifications_read_all"),
]

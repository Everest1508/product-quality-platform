from django.urls import path

from apps.uiapi import errors, products, tickets, views

app_name = "uiapi"

urlpatterns = [
    path("products/<int:pk>/nav/", products.ProductNavAPIView.as_view(), name="product_nav"),
    path("tickets/", tickets.TicketListAPIView.as_view(), name="tickets"),
    path("tickets/meta/", tickets.TicketMetaAPIView.as_view(), name="ticket_meta"),
    path("tickets/bulk-delete/", tickets.TicketBulkDeleteAPIView.as_view(), name="ticket_bulk_delete"),
    path("tickets/<int:pk>/status/", tickets.TicketStatusAPIView.as_view(), name="ticket_status"),
    path("tickets/<int:pk>/priority/", tickets.TicketPriorityAPIView.as_view(), name="ticket_priority"),
    path("tickets/<int:pk>/assign/", tickets.TicketAssignAPIView.as_view(), name="ticket_assign"),
    path("tickets/<int:pk>/deadline/", tickets.TicketDeadlineAPIView.as_view(), name="ticket_deadline"),
    path("tickets/<int:pk>/follow/", tickets.TicketFollowAPIView.as_view(), name="ticket_follow"),
    path("tickets/<int:pk>/comments/", tickets.TicketCommentAPIView.as_view(), name="ticket_comments"),
    path("tickets/<int:pk>/", tickets.TicketDetailAPIView.as_view(), name="ticket_detail"),
    path("errors/", errors.ErrorListAPIView.as_view(), name="errors"),
    path("errors/meta/", errors.ErrorMetaAPIView.as_view(), name="error_meta"),
    path("errors/<int:pk>/status/", errors.ErrorStatusAPIView.as_view(), name="error_status"),
    path("errors/<int:pk>/convert-to-ticket/", errors.ErrorConvertAPIView.as_view(), name="error_convert"),
    path("errors/<int:pk>/", errors.ErrorDetailAPIView.as_view(), name="error_detail"),
    path("company/switch/", views.CompanySwitchAPIView.as_view(), name="company_switch"),
    path("bootstrap/", views.BootstrapView.as_view(), name="bootstrap"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read-all/", views.NotificationReadAllView.as_view(), name="notifications_read_all"),
]

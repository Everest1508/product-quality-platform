from django.urls import path

from apps.ingestion import views

app_name = "ingestion"

urlpatterns = [
    path("v1/errors/capture/", views.ErrorCaptureView.as_view(), name="error_capture"),
    path("v1/feedback/", views.FeedbackView.as_view(), name="feedback"),
    path("v1/tickets/", views.TicketIngestView.as_view(), name="ticket_ingest"),
    path("v1/tickets/<int:ticket_id>/status/", views.TicketStatusView.as_view(), name="ticket_status"),
]

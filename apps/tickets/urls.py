from django.urls import path

from apps.tickets import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("kanban/", views.TicketKanbanView.as_view(), name="ticket_kanban"),
    path("create/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("<int:pk>/status/", views.TicketStatusView.as_view(), name="ticket_status"),
    path("<int:pk>/assign/", views.TicketAssignView.as_view(), name="ticket_assign"),
    path("<int:pk>/comment/", views.TicketCommentView.as_view(), name="ticket_comment"),
]

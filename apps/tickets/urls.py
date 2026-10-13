from django.urls import path

from apps.tickets import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketKanbanView.as_view(), name="ticket_board"),
    path("kanban/", views.TicketKanbanView.as_view(), name="ticket_kanban"),
    path("list/", views.TicketListView.as_view(), name="ticket_list"),
    path("create/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
    path("<int:pk>/edit/", views.TicketEditView.as_view(), name="ticket_edit"),
]

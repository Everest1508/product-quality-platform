from django.urls import path

from apps.serop import views

app_name = "serop"

urlpatterns = [
    path("teams", views.TeamsView.as_view(), name="teams"),
    path("teams/<int:team_id>", views.TeamDetailView.as_view(), name="team_detail"),
    path("teams/<int:team_id>/invite", views.TeamInviteView.as_view(), name="team_invite"),
    path("inbox", views.InboxView.as_view(), name="inbox"),
    path("inbox/<int:notification_id>/read", views.InboxReadView.as_view(), name="inbox_read"),
    path("shared-servers", views.SharedServersView.as_view(), name="shared_servers"),
    path("shared-servers/<int:server_id>/credentials", views.SharedServerCredentialsView.as_view(), name="shared_server_credentials"),
    path("shared-servers/<int:server_id>", views.SharedServerDetailView.as_view(), name="shared_server_detail"),
]

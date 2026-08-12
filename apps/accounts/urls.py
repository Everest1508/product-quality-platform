from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("company/setup/", views.CompanySetupView.as_view(), name="company_setup"),
    path("company/switch/", views.CompanySwitchView.as_view(), name="company_switch"),
    path("team/", views.TeamListView.as_view(), name="team_list"),
    path("team/invite/", views.TeamInviteView.as_view(), name="team_invite"),
    path("team/<int:pk>/edit/", views.TeamEditView.as_view(), name="team_edit"),
    path("team/<int:pk>/remove/", views.TeamRemoveView.as_view(), name="team_remove"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
]

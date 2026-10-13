from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("company/setup/", views.CompanySetupView.as_view(), name="company_setup"),
    path("team/", views.TeamListView.as_view(), name="team_list"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("oauth/authorize/", views.OAuthAuthorizeView.as_view(), name="oauth_authorize"),
    path("oauth/token/", views.OAuthTokenView.as_view(), name="oauth_token"),
    path("oauth/me/", views.OAuthMeView.as_view(), name="oauth_me"),
]

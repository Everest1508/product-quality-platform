from django.urls import path

from apps.appauth import web

app_name = "appauth_web"

urlpatterns = [
    path("", web.UsersView.as_view(), name="users"),
    path("export.csv", web.ExportView.as_view(), name="export"),
    path("<uuid:pk>/", web.UserDetailView.as_view(), name="detail"),
    path("<uuid:pk>/<str:action>/", web.UserActionView.as_view(), name="action"),
]

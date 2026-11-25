from django.urls import path

from apps.appauth import web

app_name = "appauth_web"

urlpatterns = [
    path("", web.UsersView.as_view(), name="users"),
    path("export.csv", web.ExportView.as_view(), name="export"),
    path("cards/", web.CardsView.as_view(), name="cards"),
    path("cards/<uuid:pk>/", web.CardDetailView.as_view(), name="card"),
    path("<uuid:pk>/", web.UserDetailView.as_view(), name="detail"),
    path("<uuid:pk>/<str:action>/", web.UserActionView.as_view(), name="action"),
]

from django.urls import path

from apps.serop import web

app_name = "serop_web"

urlpatterns = [
    path("", web.ServersView.as_view(), name="servers"),
    path("<int:pk>/delete/", web.ServerDeleteView.as_view(), name="server_delete"),
]

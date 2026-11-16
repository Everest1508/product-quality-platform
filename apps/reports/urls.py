from django.urls import path

from . import views

app_name = "reports"
urlpatterns = [
    path("", views.HubView.as_view(), name="hub"),
    path("<slug:key>/", views.RunView.as_view(), name="run"),
]

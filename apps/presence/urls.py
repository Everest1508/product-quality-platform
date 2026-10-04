from django.urls import path

from apps.presence import views

app_name = "presence"

urlpatterns = [
    path("beat/", views.beat, name="beat"),
]

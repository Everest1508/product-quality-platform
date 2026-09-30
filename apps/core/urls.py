from django.urls import path

from apps.core import api

app_name = "core"

urlpatterns = [
    path("v1/version/", api.VersionView.as_view(), name="version"),
    path("v1/changelog/", api.ChangelogView.as_view(), name="changelog"),
]

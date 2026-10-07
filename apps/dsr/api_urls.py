from django.urls import path

from apps.dsr import api

app_name = "dsr_api"

urlpatterns = [
    path("v1/users/me/", api.MeView.as_view(), name="me"),
    path("v1/projects/", api.ProjectsView.as_view(), name="projects"),
    path("v1/activities/today/", api.ActivitiesView.as_view(), name="activities"),
    path("v1/dsr/today/", api.TodayView.as_view(), name="today"),
    path("v1/dsr/", api.DSRCreateView.as_view(), name="create"),
    path("v1/dsr/<int:pk>/", api.DSRDetailView.as_view(), name="detail"),
]

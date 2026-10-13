from django.urls import path

from apps.errors import views

app_name = "errors"

urlpatterns = [
    path("", views.ErrorShellView.as_view(), name="error_list"),
    path("create/", views.ErrorShellView.as_view(), name="error_create"),
    path("<int:pk>/", views.ErrorDetailView.as_view(), name="error_detail"),
]

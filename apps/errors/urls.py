from django.urls import path

from apps.errors import views

app_name = "errors"

urlpatterns = [
    path("", views.ErrorShellView.as_view(), name="error_list"),
    path("create/", views.ErrorShellView.as_view(), name="error_create"),
    path("<int:pk>/", views.ErrorDetailView.as_view(), name="error_detail"),
    # The home dashboard still posts to these two; they go when it moves.
    path("<int:pk>/ignore/", views.ErrorIgnoreView.as_view(), name="error_ignore"),
    path("<int:pk>/resolve/", views.ErrorResolveView.as_view(), name="error_resolve"),
]

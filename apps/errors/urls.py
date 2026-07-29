from django.urls import path

from apps.errors import views

app_name = "errors"

urlpatterns = [
    path("", views.ErrorListView.as_view(), name="error_list"),
    path("create/", views.ErrorCreateView.as_view(), name="error_create"),
    path("<int:pk>/", views.ErrorDetailView.as_view(), name="error_detail"),
    path("<int:pk>/status/", views.ErrorStatusView.as_view(), name="error_status"),
    path("<int:pk>/ignore/", views.ErrorIgnoreView.as_view(), name="error_ignore"),
    path("<int:pk>/resolve/", views.ErrorResolveView.as_view(), name="error_resolve"),
    path("<int:pk>/convert-to-ticket/", views.ErrorConvertToTicketView.as_view(), name="error_convert_to_ticket"),
]

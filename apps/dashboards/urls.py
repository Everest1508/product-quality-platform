from django.urls import path

from apps.dashboards import views

app_name = "dashboards"

urlpatterns = [
    path("", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("product/<int:product_pk>/", views.ProductDashboardView.as_view(), name="product_dashboard"),
]

from django.urls import path

from apps.dashboards import views

app_name = "dashboards"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="index"),
    path("", views.DashboardView.as_view(), name="admin_dashboard"),
    path("product/<int:product_pk>/", views.ProductDashboardView.as_view(), name="product_dashboard"),
    path("audit/", views.AuditLogView.as_view(), name="audit_log"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
]

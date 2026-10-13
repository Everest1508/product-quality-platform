from django.urls import path

from apps.dashboards import views

app_name = "dashboards"

urlpatterns = [
    # `index` is the real home page. The singular `/dashboard/` path is a
    # redirect to it, declared in core/urls.py.
    path("", views.DashboardShellView.as_view(), name="index"),
    path("", views.DashboardShellView.as_view(), name="admin_dashboard"),
    path("product/<int:product_pk>/", views.ProductDashboardView.as_view(), name="product_dashboard"),
    path("audit/", views.AuditLogView.as_view(), name="audit_log"),
    path("reports/", views.DashboardShellView.as_view(), name="reports"),
]

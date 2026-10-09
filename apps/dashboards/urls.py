from django.urls import path

from apps.dashboards import views

app_name = "dashboards"

urlpatterns = [
    # `index` is the real home page. The singular `/dashboard/` path is a
    # redirect to it, declared in core/urls.py.
    path("", views.DashboardView.as_view(), name="index"),
    path("", views.DashboardView.as_view(), name="admin_dashboard"),
    path("product/<int:product_pk>/", views.ProductDashboardView.as_view(), name="product_dashboard"),
    path("audit/", views.AuditLogView.as_view(), name="audit_log"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path("todos/", views.TodoListView.as_view(), name="todos"),
    path("todos/<int:pk>/toggle/", views.TodoToggleView.as_view(), name="todo_toggle"),
    path("todos/<int:pk>/delete/", views.TodoDeleteView.as_view(), name="todo_delete"),
    path("quote/", views.QuoteView.as_view(), name="quote"),
]

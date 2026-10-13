from django.urls import path

from apps.payroll import views

app_name = "payroll"

urlpatterns = [
    path("", views.PayrollAdminShellView.as_view(), name="run_list"),
    path("preview/", views.PayrollAdminShellView.as_view(), name="preview"),
    path("runs/<int:pk>/", views.PayrollRunShellView.as_view(), name="run_detail"),
    path("payslips/<int:pk>/", views.PayslipShellView.as_view(), name="payslip"),
    # "mine" comes first so a payslip pk cannot be probed through the admin
    # route, and so the self-scoped pair reads as the default entry point.
    path("me/", views.MyPayslipsShellView.as_view(), name="my_payslips"),
    path("me/<int:pk>/", views.MyPayslipShellView.as_view(), name="my_payslip"),
    path("holidays/", views.PayrollAdminShellView.as_view(), name="holidays"),
    path("profiles/", views.PayrollAdminShellView.as_view(), name="profiles"),
]

from django.urls import path

from apps.payroll import views

app_name = "payroll"

urlpatterns = [
    path("", views.PayrollRunListView.as_view(), name="run_list"),
    path("preview/", views.PayrollPreviewView.as_view(), name="preview"),
    path("runs/<int:pk>/", views.PayrollRunDetailView.as_view(), name="run_detail"),
    path("runs/<int:pk>/lock/", views.PayrollRunLockView.as_view(), name="run_lock"),
    path("payslips/<int:pk>/", views.PayslipDetailView.as_view(), name="payslip"),
    # "mine" comes first so a payslip pk cannot be probed through the admin
    # route, and so the self-scoped pair reads as the default entry point.
    path("me/", views.MyPayslipListView.as_view(), name="my_payslips"),
    path("me/<int:pk>/", views.MyPayslipDetailView.as_view(), name="my_payslip"),
    path("holidays/", views.HolidayListView.as_view(), name="holidays"),
    path("holidays/<int:pk>/delete/", views.HolidayDeleteView.as_view(), name="holiday_delete"),
    path("profiles/", views.PayrollProfileListView.as_view(), name="profiles"),
]

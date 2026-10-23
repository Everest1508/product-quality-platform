from django.urls import path

from apps.costing import views

app_name = "costing"

urlpatterns = [
    path("", views.EstimateListView.as_view(), name="estimate_list"),
    path("export.csv", views.EstimateExportView.as_view(), name="estimate_export"),
    path("new/", views.EstimateFormView.as_view(), name="estimate_new"),
    path("calc/", views.EstimateCalcView.as_view(), name="estimate_calc"),
    path("<int:pk>/", views.EstimateDetailView.as_view(), name="estimate_detail"),
    path("<int:pk>/edit/", views.EstimateFormView.as_view(), name="estimate_edit"),
    path("<int:pk>/delete/", views.EstimateDeleteView.as_view(), name="estimate_delete"),
    path("<int:pk>/duplicate/", views.EstimateDuplicateView.as_view(), name="estimate_duplicate"),
    path("<int:pk>/quote/", views.EstimateQuoteView.as_view(), name="estimate_quote"),
]

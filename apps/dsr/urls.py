from django.urls import path

from apps.dsr import views

app_name = "dsr"

urlpatterns = [
    path("", views.DSRSheetView.as_view(), name="dsr_sheet"),
]

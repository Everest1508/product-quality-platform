from django.urls import path
from apps.dsr import views

app_name = "dsr"

urlpatterns = [
    path("", views.DSRSheetView.as_view(), name="dsr_sheet"),
    path("suggestion/add/", views.DSRSuggestionAddView.as_view(), name="dsr_suggestion_add"),
    path("add/", views.DSREntryAddView.as_view(), name="dsr_add"),
    path("<int:pk>/update/", views.DSREntryUpdateView.as_view(), name="dsr_update"),
    path("<int:pk>/delete/", views.DSREntryDeleteView.as_view(), name="dsr_delete"),
]

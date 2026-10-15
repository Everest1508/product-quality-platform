from django.urls import path

from apps.expenses import views

app_name = "expenses"

urlpatterns = [
    path("", views.ExpenseListView.as_view(), name="expense_list"),
    path("export.csv", views.ExpenseExportView.as_view(), name="expense_export"),
    path("<int:pk>/", views.ExpenseEditView.as_view(), name="expense_edit"),
    path("<int:pk>/delete/", views.ExpenseDeleteView.as_view(), name="expense_delete"),
]

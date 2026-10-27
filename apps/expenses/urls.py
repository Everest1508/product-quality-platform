from django.urls import path

from apps.expenses import views

app_name = "expenses"

urlpatterns = [
    path("", views.ExpenseListView.as_view(), name="expense_list"),
    path("export.csv", views.ExpenseExportView.as_view(), name="expense_export"),
    path("salary-all/", views.ExpenseSalaryAllView.as_view(), name="expense_salary_all"),
    path("<int:pk>/", views.ExpenseEditView.as_view(), name="expense_edit"),
    path("<int:pk>/delete/", views.ExpenseDeleteView.as_view(), name="expense_delete"),
    path("<int:pk>/salary/", views.ExpenseSalaryView.as_view(), name="expense_salary"),
    path("<int:pk>/repaid/", views.ExpenseRepaidView.as_view(), name="expense_repaid"),
    path("<int:pk>/comment/", views.ExpenseCommentView.as_view(), name="expense_comment"),
    path("<int:pk>/comment/<int:comment_pk>/delete/", views.ExpenseCommentDeleteView.as_view(), name="expense_comment_delete"),
]

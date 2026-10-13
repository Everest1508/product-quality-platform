from django.urls import path

from apps.automation import views

app_name = "automation"

urlpatterns = [
    path("", views.RuleShellView.as_view(), name="rule_list"),
    path("create/", views.RuleShellView.as_view(), name="rule_create"),
    path("<int:pk>/edit/", views.RuleEditView.as_view(), name="rule_edit"),
]

from django.urls import path

from apps.automation import views

app_name = "automation"

urlpatterns = [
    path("", views.RuleListView.as_view(), name="rule_list"),
    path("create/", views.RuleCreateView.as_view(), name="rule_create"),
    path("<int:pk>/edit/", views.RuleEditView.as_view(), name="rule_edit"),
    path("<int:pk>/delete/", views.RuleDeleteView.as_view(), name="rule_delete"),
    path("<int:pk>/toggle/", views.RuleToggleView.as_view(), name="rule_toggle"),
]

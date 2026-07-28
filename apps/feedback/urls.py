from django.urls import path

from apps.feedback import views

app_name = "feedback"

urlpatterns = [
    path("", views.SurveyListView.as_view(), name="survey_list"),
    path("create/", views.SurveyCreateView.as_view(), name="survey_create"),
    path("<int:pk>/", views.SurveyDetailView.as_view(), name="survey_detail"),
    path("<int:pk>/toggle/", views.SurveyToggleView.as_view(), name="survey_toggle"),
    path("<int:pk>/delete/", views.SurveyDeleteView.as_view(), name="survey_delete"),
    path("respond/<int:pk>/", views.PublicSurveyView.as_view(), name="public_survey"),
    path("cs-hub/", views.CustomerSuccessHubView.as_view(), name="cs_hub"),
]

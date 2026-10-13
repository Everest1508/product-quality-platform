from django.urls import path

from apps.feedback import views

app_name = "feedback"

urlpatterns = [
    path("", views.SurveyShellView.as_view(), name="survey_list"),
    path("create/", views.SurveyShellView.as_view(), name="survey_create"),
    path("<int:pk>/", views.SurveyDetailView.as_view(), name="survey_detail"),
    path("respond/<int:pk>/", views.PublicSurveyView.as_view(), name="public_survey"),
    path("cs-hub/", views.SurveyShellView.as_view(), name="cs_hub"),
]

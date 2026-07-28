from django.contrib import admin

from apps.feedback.models import SentimentRecord, Survey, SurveyResponse


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("name", "survey_type", "status", "product", "company")
    list_filter = ("survey_type", "status")


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ("survey", "score", "contact_name", "created_at")
    list_filter = ("survey__survey_type",)


@admin.register(SentimentRecord)
class SentimentRecordAdmin(admin.ModelAdmin):
    list_display = ("product", "source", "score", "recorded_at")
    list_filter = ("source",)

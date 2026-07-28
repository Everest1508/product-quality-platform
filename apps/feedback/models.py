from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TenantScopedModel


class Survey(TenantScopedModel):
    class SurveyType(models.TextChoices):
        NPS = "nps", "Net Promoter Score"
        CSAT = "csat", "Customer Satisfaction"
        CES = "ces", "Customer Effort Score"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="surveys",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    survey_type = models.CharField(
        max_length=10,
        choices=SurveyType.choices,
        default=SurveyType.NPS,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_surveys",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_survey_type_display()})"

    @property
    def response_count(self):
        return self.responses.count()

    def score_range(self):
        if self.survey_type == "nps":
            return range(0, 11)
        elif self.survey_type == "csat":
            return range(1, 6)
        elif self.survey_type == "ces":
            return range(1, 8)
        return range(0, 11)

    def score_label(self, score):
        if self.survey_type == "nps":
            if score <= 6:
                return "Detractor"
            elif score <= 8:
                return "Passive"
            return "Promoter"
        elif self.survey_type == "csat":
            if score <= 2:
                return "Unsatisfied"
            elif score <= 3:
                return "Neutral"
            return "Satisfied"
        elif self.survey_type == "ces":
            if score <= 3:
                return "Difficult"
            elif score <= 5:
                return "Neutral"
            return "Easy"
        return ""

    def compute_nps(self):
        if self.survey_type != "nps":
            return None
        scores = list(self.responses.values_list("score", flat=True))
        if not scores:
            return None
        total = len(scores)
        promoters = sum(1 for s in scores if s >= 9)
        detractors = sum(1 for s in scores if s <= 6)
        return round(((promoters - detractors) / total) * 100)

    def compute_avg_score(self):
        from django.db.models import Avg
        result = self.responses.aggregate(avg=Avg("score"))
        if result["avg"] is not None:
            return round(result["avg"], 1)
        return None


class SurveyResponse(TenantScopedModel):
    survey = models.ForeignKey(
        Survey,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    comment = models.TextField(blank=True, default="")
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    user_ref = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"Response {self.score}/10 for {self.survey.name}"


class SentimentRecord(TenantScopedModel):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="sentiment_records",
    )
    source = models.CharField(
        max_length=20,
        choices=[
            ("survey", "Survey"),
            ("feedback", "Feedback"),
            ("support", "Support"),
            ("manual", "Manual"),
        ],
        default="survey",
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Sentiment score from -1.0 (negative) to +1.0 (positive)",
        validators=[MinValueValidator(-1), MaxValueValidator(1)],
    )
    summary = models.TextField(blank=True, default="")
    recorded_at = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Sentiment {self.score} ({self.source}) for {self.product.name}"

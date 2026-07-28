import hashlib

from django.utils import timezone
from rest_framework import serializers

from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback, IngestedTicket


class ErrorCaptureSerializer(serializers.Serializer):
    error_type = serializers.CharField(max_length=255, required=False, default="")
    message = serializers.CharField(max_length=1000)
    stacktrace = serializers.CharField(required=False, default="")
    environment = serializers.CharField(max_length=20, required=False, default="production")
    user_ref = serializers.CharField(max_length=255, required=False, default="")
    page = serializers.CharField(max_length=500, required=False, default="")
    device = serializers.CharField(max_length=255, required=False, default="")
    os = serializers.CharField(max_length=100, required=False, default="")
    browser = serializers.CharField(max_length=100, required=False, default="")
    version = serializers.CharField(max_length=50, required=False, default="")
    request_payload = serializers.JSONField(required=False, default=None)
    extra = serializers.JSONField(required=False, default=dict)

    def create(self, validated_data):
        api_key = self.context["api_key"]
        product = api_key.product
        company = product.company

        fingerprint = hashlib.sha256(
            f"{validated_data.get('error_type', '')}:{validated_data['message']}:"
            f"{validated_data.get('stacktrace', '')[:500]}".encode()
        ).hexdigest()[:32]

        error_group, created = ErrorGroup.objects.get_or_create(
            product=product,
            fingerprint=fingerprint,
            defaults={
                "company": company,
                "title": validated_data["message"][:500],
                "error_type": validated_data.get("error_type", ""),
            },
        )

        if not created:
            error_group.occurrence_count += 1
            error_group.last_seen = timezone.now()
            error_group.save(update_fields=["occurrence_count", "last_seen"])

        version_obj = None
        if validated_data.get("version"):
            from apps.products.models import ProductVersion
            version_obj = ProductVersion.objects.filter(
                product=product,
                version_string=validated_data["version"],
            ).first()

        occurrence = ErrorOccurrence.objects.create(
            error_group=error_group,
            company=company,
            version=version_obj,
            environment=validated_data.get("environment", "production"),
            stacktrace=validated_data.get("stacktrace", ""),
            user_ref=validated_data.get("user_ref", ""),
            page=validated_data.get("page", ""),
            device=validated_data.get("device", ""),
            os=validated_data.get("os", ""),
            browser=validated_data.get("browser", ""),
            request_payload=validated_data.get("request_payload"),
            raw_data=validated_data.get("extra"),
        )

        return {
            "error_group_id": error_group.id,
            "occurrence_id": occurrence.id,
            "fingerprint": fingerprint,
            "occurrence_count": error_group.occurrence_count,
            "created": created,
        }


class FeedbackSerializer(serializers.Serializer):
    user_ref = serializers.CharField(max_length=255, required=False, default="")
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, default="")
    screenshot_url = serializers.URLField(required=False, default="")
    version = serializers.CharField(max_length=50, required=False, default="")

    def create(self, validated_data):
        api_key = self.context["api_key"]
        product = api_key.product
        company = product.company

        version_obj = None
        if validated_data.get("version"):
            from apps.products.models import ProductVersion
            version_obj = ProductVersion.objects.filter(
                product=product,
                version_string=validated_data["version"],
            ).first()

        feedback = Feedback.objects.create(
            product=product,
            company=company,
            version=version_obj,
            user_ref=validated_data.get("user_ref", ""),
            rating=validated_data["rating"],
            comment=validated_data.get("comment", ""),
            screenshot_url=validated_data.get("screenshot_url", ""),
        )
        return {"feedback_id": feedback.id}


class TicketIngestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500)
    description = serializers.CharField(required=False, default="")
    ticket_type = serializers.ChoiceField(
        choices=[("bug", "Bug"), ("feature", "Feature"), ("question", "Question")],
        default="bug",
    )
    user_ref = serializers.CharField(max_length=255, required=False, default="")
    external_id = serializers.CharField(max_length=255, required=False, default="")
    metadata = serializers.JSONField(required=False, default=None)

    def create(self, validated_data):
        api_key = self.context["api_key"]
        product = api_key.product
        company = product.company

        ticket = IngestedTicket.objects.create(
            product=product,
            company=company,
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            ticket_type=validated_data.get("ticket_type", "bug"),
            user_ref=validated_data.get("user_ref", ""),
            external_id=validated_data.get("external_id", ""),
            metadata=validated_data.get("metadata"),
        )
        return {"ticket_id": ticket.id}


class TicketStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()

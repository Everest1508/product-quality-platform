import hashlib

from django.utils import timezone
from rest_framework import serializers

from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback, IngestedTicket
from apps.products.webhook import notify_error_captured, notify_feedback_created, notify_ticket_created
from apps.tickets.models import Ticket


class ErrorCaptureSerializer(serializers.Serializer):
    error_type = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    message = serializers.CharField(max_length=1000)
    stacktrace = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    environment = serializers.CharField(max_length=20, required=False, allow_null=True, allow_blank=True, default="production")
    user_ref = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    page = serializers.CharField(max_length=500, required=False, allow_null=True, allow_blank=True, default="")
    device = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    os = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True, default="")
    browser = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True, default="")
    version = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default="")
    request_payload = serializers.JSONField(required=False, allow_null=True, default=None)
    extra = serializers.JSONField(required=False, allow_null=True, default=dict)

    def create(self, validated_data):
        api_key = self.context["api_key"]
        product = api_key.product
        company = product.company

        fingerprint = hashlib.sha256(
            f"{validated_data.get('error_type') or ''}:{validated_data['message']}:"
            f"{(validated_data.get('stacktrace') or '')[:500]}".encode()
        ).hexdigest()[:32]

        error_group, created = ErrorGroup.objects.get_or_create(
            product=product,
            fingerprint=fingerprint,
            defaults={
                "company": company,
                "title": validated_data["message"][:500],
                "error_type": validated_data.get("error_type") or "",
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
            environment=validated_data.get("environment") or "production",
            stacktrace=validated_data.get("stacktrace") or "",
            user_ref=validated_data.get("user_ref") or "",
            page=validated_data.get("page") or "",
            device=validated_data.get("device") or "",
            os=validated_data.get("os") or "",
            browser=validated_data.get("browser") or "",
            request_payload=validated_data.get("request_payload"),
            raw_data=validated_data.get("extra"),
        )

        notify_error_captured(error_group, occurrence)

        return {
            "error_group_id": error_group.id,
            "occurrence_id": occurrence.id,
            "fingerprint": fingerprint,
            "occurrence_count": error_group.occurrence_count,
            "created": created,
        }


class FeedbackSerializer(serializers.Serializer):
    user_ref = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    screenshot_url = serializers.URLField(required=False, allow_null=True, allow_blank=True, default="")
    version = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default="")

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
        notify_feedback_created(feedback)
        return {"feedback_id": feedback.id}


class TicketIngestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=500)
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    ticket_type = serializers.ChoiceField(
        choices=[("bug", "Bug"), ("feature", "Feature"), ("question", "Question")],
        default="bug",
        allow_blank=True,
    )
    user_ref = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    external_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, allow_null=True, default=None)

    def create(self, validated_data):
        api_key = self.context["api_key"]
        product = api_key.product
        company = product.company

        ingested = IngestedTicket.objects.create(
            product=product,
            company=company,
            title=validated_data["title"],
            description=validated_data.get("description") or "",
            ticket_type=validated_data.get("ticket_type") or "bug",
            user_ref=validated_data.get("user_ref") or "",
            external_id=validated_data.get("external_id") or "",
            metadata=validated_data.get("metadata"),
        )

        ticket = Ticket.objects.create(
            product=product,
            company=company,
            title=validated_data["title"],
            description=validated_data.get("description", ""),
            ticket_type=validated_data.get("ticket_type", "bug"),
            source=Ticket.Source.AUTO,
        )
        notify_ticket_created(ticket)
        return {"ticket_id": ingested.id, "ui_ticket_id": ticket.id}


class TicketStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()

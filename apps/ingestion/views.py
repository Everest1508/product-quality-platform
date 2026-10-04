from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.ingestion.serializers import (
    ErrorCaptureSerializer,
    FeedbackSerializer,
    TicketIngestSerializer,
)
from apps.products.models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Missing or invalid Authorization header. Use: Bearer <api_key>")

        raw_key = auth_header[7:].strip()
        if not raw_key:
            raise AuthenticationFailed("Empty API key.")

        api_key = APIKey.validate_key(raw_key)
        if not api_key:
            raise AuthenticationFailed("Invalid or revoked API key.")

        return (None, api_key)


class IsAuthenticatedAPIKey(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, APIKey)


class APIKeyRateThrottle(SimpleRateThrottle):
    """Rate limit per API key, not per IP.

    The old default was DRF's anonymous throttle, which keys on the client IP.
    These requests carry `request.user = None`, so every customer behind one NAT
    shared a single 60/minute budget and real errors were rejected with 429.
    """

    scope = "apikey"

    def get_cache_key(self, request, view):
        key = getattr(request, "auth", None)
        if key is None:
            return self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": f"key{key.pk}"}


class ErrorCaptureView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticatedAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    def post(self, request):
        serializer = ErrorCaptureSerializer(
            data=request.data,
            context={"api_key": request.auth},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class FeedbackView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticatedAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    def post(self, request):
        serializer = FeedbackSerializer(
            data=request.data,
            context={"api_key": request.auth},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class TicketIngestView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticatedAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    def post(self, request):
        serializer = TicketIngestSerializer(
            data=request.data,
            context={"api_key": request.auth},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class TicketStatusView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticatedAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    def get(self, request, ticket_id):
        from apps.ingestion.models import IngestedTicket
        ticket = IngestedTicket.objects.filter(
            pk=ticket_id,
            product=request.auth.product,
        ).first()
        if not ticket:
            return Response({"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": ticket.id,
            "title": ticket.title,
            "status": "ingested",
            "created_at": ticket.created_at.isoformat(),
        })

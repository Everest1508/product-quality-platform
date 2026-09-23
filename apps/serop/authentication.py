from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import ExternalAccessToken


class ExternalTokenAuthentication(BaseAuthentication):
    """Authenticates Serop desktop app requests via the bearer token issued
    by /oauth/token/ (apps.accounts.models.ExternalAccessToken). Unlike
    apps.ingestion's APIKeyAuthentication, request.user is set to the real
    CRM user so normal Membership/Company queries work directly."""

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Missing or invalid Authorization header. Use: Bearer <token>")

        raw_token = auth_header[len("Bearer "):].strip()
        if not raw_token:
            raise AuthenticationFailed("Empty token.")

        token_obj = ExternalAccessToken.validate(raw_token)
        if not token_obj:
            raise AuthenticationFailed("Invalid or revoked token.")

        return (token_obj.user, token_obj)

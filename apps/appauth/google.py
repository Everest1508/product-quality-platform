import jwt
from django.conf import settings

from apps.appauth.service import AuthError

_JWKS = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True)
_ISSUERS = ["https://accounts.google.com", "accounts.google.com"]


def verify_google_id_token(raw):
    """Signature (Google JWKS), aud, iss, exp and email_verified. Returns the verified claims.
    Tests patch this function; nothing else in the app talks to Google."""
    audiences = settings.GOOGLE_CLIENT_IDS
    bad = AuthError("invalid_google_token", "Invalid Google token.", 401)
    if not audiences or not isinstance(raw, str) or not raw:
        raise bad
    try:
        key = _JWKS.get_signing_key_from_jwt(raw).key
        claims = jwt.decode(raw, key, algorithms=["RS256"], audience=audiences, issuer=_ISSUERS,
                            options={"require": ["exp", "iss", "aud", "sub"]})
    except jwt.PyJWTError:
        raise bad
    if claims.get("email_verified") not in (True, "true") or not claims.get("email"):
        raise bad
    return claims

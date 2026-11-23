import jwt
from django.conf import settings

from apps.appauth.service import AuthError

_JWKS = jwt.PyJWKClient("https://appleid.apple.com/auth/keys", cache_keys=True)


def verify_apple_identity_token(raw):
    """Signature (Apple JWKS), iss, aud (= app bundle ID) and exp. Returns claims with `email_verified`
    normalised to a bool. Tests patch this function."""
    bad = AuthError("invalid_apple_token", "Invalid Apple token.", 401)
    if not settings.APPLE_CLIENT_IDS or not isinstance(raw, str) or not raw:
        raise bad
    try:
        key = _JWKS.get_signing_key_from_jwt(raw).key
        claims = jwt.decode(raw, key, algorithms=["RS256"], audience=settings.APPLE_CLIENT_IDS,
                            issuer="https://appleid.apple.com", options={"require": ["exp", "iss", "aud", "sub"]})
    except jwt.PyJWTError:
        raise bad
    # Apple sends email_verified as the string "true". Relay (hidden) addresses are verified by Apple.
    if "email" in claims and str(claims.get("email_verified")).lower() != "true":
        claims.pop("email")
    return claims

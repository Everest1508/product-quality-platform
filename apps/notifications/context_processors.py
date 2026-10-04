from django.conf import settings


def webpush(request):
    """The public key the browser needs to subscribe. Empty means push is off."""
    return {"webpush_public_key": getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", "")}

import uuid

from django.db import models


class AppUser(models.Model):
    """An end user of the CardSnap mobile app. Not a CRM `accounts.User`: these
    people are not company members and must never reach the web UI."""

    PROVIDERS = [("password", "Password"), ("google", "Google"), ("apple", "Apple")]
    STATUSES = [("active", "Active"), ("revoked", "Revoked"), ("deleted", "Deleted")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)  # always stored lowercase
    password_hash = models.CharField(max_length=256, null=True, blank=True)
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
    apple_sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, default="")
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    auth_provider = models.CharField(max_length=10, choices=PROVIDERS, default="password")
    status = models.CharField(max_length=10, choices=STATUSES, default="active", db_index=True)
    email_verified = models.BooleanField(default=False)
    # Bumped on revoke / force-logout / password change: every access token minted before dies at once.
    token_version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_login_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True, default="")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_users"

    def __str__(self):
        return self.email


class DeletedAppUser(models.Model):
    """What we keep for analysis when a person deletes their account: the AppUser row itself is erased."""

    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    auth_provider = models.CharField(max_length=10, blank=True, default="")
    email_verified = models.BooleanField(default=False)
    signed_up_at = models.DateTimeField()
    last_login_at = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "app_deleted_users"
        ordering = ["-deleted_at"]


class AppRefreshToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="refresh_tokens")
    token_hash = models.CharField(max_length=64, unique=True)  # sha256 hex; the raw token is never stored
    family = models.UUIDField(db_index=True)  # one login = one family; rotation keeps it
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    device_info = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "app_refresh_tokens"


class AppAuthEvent(models.Model):
    user = models.ForeignKey(AppUser, null=True, on_delete=models.SET_NULL, related_name="events")
    event = models.CharField(max_length=20)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "app_auth_events"
        ordering = ["-created_at", "-id"]


class MailflareConfig(models.Model):
    """The one outgoing-mail setting for the whole install (pk=1), entered by an admin in the UI.
    The API key is Fernet-encrypted and never shown again. Env vars (MAILFLARE_*) are the fallback."""

    api_url = models.URLField(max_length=300)
    mailbox_id = models.CharField(max_length=120)
    from_address = models.EmailField()  # the one mailbox Mailflare allows us to send from
    api_key_encrypted = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        db_table = "app_mailflare_config"


class MailLog(models.Model):
    """One row per email the CRM tried to send through Mailflare. No body, never the key."""

    to_addrs = models.CharField(max_length=500)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=10, db_index=True)  # sent | failed
    error = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "app_mail_log"
        ordering = ["-created_at", "-id"]

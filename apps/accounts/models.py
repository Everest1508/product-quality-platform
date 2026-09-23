import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    discord_id = models.CharField(max_length=64, blank=True, default="", help_text="Discord user snowflake ID, used to mention the user in webhook notifications.")

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"


class Company(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MembershipManager(models.Manager):
    def for_company(self, company):
        return super().get_queryset().filter(company=company)


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        DEVELOPER = "developer", "Developer"
        SUPPORT = "support", "Support"
        VIEWER = "viewer", "Viewer"

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MembershipManager()

    class Meta:
        unique_together = ("user", "company")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} @ {self.company.name} ({self.role})"


class ExternalAuthCode(models.Model):
    """One-time code handed to an external client (e.g. the Serop desktop app)
    after a user signs in via /oauth/authorize/, exchanged once for an
    ExternalAccessToken via /oauth/token/."""

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="external_auth_codes",
    )
    client_id = models.CharField(max_length=100)
    redirect_uri = models.URLField()
    code_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"auth code for {self.user.username} ({self.client_id})"

    @classmethod
    def issue(cls, user, client_id, redirect_uri, ttl_seconds=120):
        raw_code = secrets.token_urlsafe(32)
        code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
        obj = cls.objects.create(
            user=user,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_hash=code_hash,
            expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        )
        return obj, raw_code

    @classmethod
    def exchange(cls, raw_code):
        code_hash = hashlib.sha256(raw_code.encode()).hexdigest()
        try:
            obj = cls.objects.select_related("user").get(code_hash=code_hash, used_at__isnull=True)
        except cls.DoesNotExist:
            return None
        if obj.expires_at < timezone.now():
            return None
        obj.used_at = timezone.now()
        obj.save(update_fields=["used_at"])
        return obj.user


class ExternalAccessToken(models.Model):
    """Long-lived bearer token for an external client, issued after an
    ExternalAuthCode exchange. Same hash-and-validate shape as products.APIKey."""

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="external_tokens",
    )
    client_id = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"access token for {self.user.username} ({self.client_id})"

    @classmethod
    def create_token(cls, user, client_id="serop"):
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        obj = cls.objects.create(user=user, client_id=client_id, token_hash=token_hash)
        return obj, raw_token

    @classmethod
    def validate(cls, raw_token):
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        try:
            obj = cls.objects.select_related("user").get(token_hash=token_hash, revoked_at__isnull=True)
        except cls.DoesNotExist:
            return None
        obj.last_used_at = timezone.now()
        obj.save(update_fields=["last_used_at"])
        return obj

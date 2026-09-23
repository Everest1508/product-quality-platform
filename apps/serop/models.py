from django.conf import settings
from django.db import models

from apps.accounts.models import Company


class SeropNotification(models.Model):
    """Inbox item for the Serop desktop app (team-invite notices, etc.)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="serop_notifications",
    )
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    payload = models.JSONField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} -> {self.user.username}"

    def as_json(self):
        return {
            "id": str(self.pk),
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "payload": self.payload,
            "readAt": self.read_at.isoformat() if self.read_at else None,
            "createdAt": self.created_at.isoformat(),
        }


class SeropSharedServer(models.Model):
    """A local Serop server profile shared with a CRM company ("team")."""

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="serop_shared_servers",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="serop_owned_shared_servers",
    )
    name = models.CharField(max_length=255)
    host = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    connection_type = models.CharField(max_length=20, default="password")
    private_key_path = models.CharField(max_length=500, null=True, blank=True)
    project_path = models.CharField(max_length=500, null=True, blank=True)
    is_shareable = models.BooleanField(default=True)
    encrypted_password = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.username}@{self.host})"

    def as_json(self):
        return {
            "id": str(self.pk),
            "teamId": str(self.company_id),
            "ownerId": str(self.owner_id),
            "name": self.name,
            "host": self.host,
            "username": self.username,
            "connectionType": self.connection_type,
            "privateKeyPath": self.private_key_path,
            "projectPath": self.project_path,
            "isShareable": self.is_shareable,
            "hasStoredPassword": bool(self.encrypted_password),
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

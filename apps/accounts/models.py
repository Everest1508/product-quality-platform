from django.contrib.auth.models import AbstractUser
from django.db import models


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

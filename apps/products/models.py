import secrets
import hashlib

from django.db import models

from apps.core.models import TenantScopedModel


class Product(TenantScopedModel):
    ENVIRONMENT_CHOICES = [
        ("production", "Production"),
        ("staging", "Staging"),
        ("dev", "Development"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True, default="")
    default_environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        default="production",
    )
    discord_webhook_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TenantScopedModel.Meta):
        unique_together = ("company", "slug")
        ordering = ["name"]

    def __str__(self):
        return f"{self.company.name} / {self.name}"


class ProductAccess(TenantScopedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="access_records",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="product_accesses",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        unique_together = ("product", "user")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} -> {self.product.name}"


class ProductVersion(TenantScopedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_string = models.CharField(max_length=50)
    released_at = models.DateTimeField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantScopedModel.Meta):
        unique_together = ("product", "version_string")
        ordering = ["-released_at"]

    def __str__(self):
        return f"{self.product.name} v{self.version_string}"


class APIKeyManager(models.Manager):
    def for_company(self, company):
        return super().get_queryset().filter(product__company=company)


class APIKey(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=100, blank=True, default="default")
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    prefix = models.CharField(max_length=8, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    objects = APIKeyManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}...) for {self.product.name}"

    @classmethod
    def create_key(cls, product, name="default"):
        raw_key = secrets.token_hex(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:8]
        api_key = cls.objects.create(
            product=product,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
        )
        return api_key, raw_key

    @classmethod
    def validate_key(cls, raw_key):
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        try:
            api_key = cls.objects.select_related("product", "product__company").get(
                key_hash=key_hash,
                is_active=True,
                revoked_at__isnull=True,
            )
            from django.utils import timezone
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=["last_used_at"])
            return api_key
        except cls.DoesNotExist:
            return None

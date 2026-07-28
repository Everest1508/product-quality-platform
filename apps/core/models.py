from django.db import models


class TenantScopedManager(models.Manager):
    def for_company(self, company):
        return super().get_queryset().filter(company=company)


class TenantScopedModel(models.Model):
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
    )
    objects = TenantScopedManager()

    class Meta:
        abstract = True

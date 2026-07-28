from django.contrib import admin

from apps.products.models import APIKey, Product, ProductVersion


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "slug", "default_environment", "created_at")
    list_filter = ("default_environment",)
    search_fields = ("name", "slug", "company__name")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductVersion)
class ProductVersionAdmin(admin.ModelAdmin):
    list_display = ("product", "version_string", "is_current", "released_at")
    list_filter = ("is_current",)
    search_fields = ("version_string", "product__name")


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "prefix", "is_active", "last_used_at", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "product__name")
    readonly_fields = ("key_hash", "prefix", "last_used_at")

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.ingestion.urls")),
    path("products/", include("apps.products.urls")),
    path("errors/", include("apps.errors.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("automation/", include("apps.automation.urls")),
    path("feedback/", include("apps.feedback.urls")),
    path("dashboards/", include("apps.dashboards.urls")),
    path("", include("apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from apps.leads.views import LeadWebhookView
from django.urls import include, path

from apps.core import befui
from django.views.generic import RedirectView

from apps.core.assets import css as app_css
from apps.core.brand import brand_file, favicon_ico
from apps.core.search import SearchView
from apps.core.pwa import manifest, offline, service_worker

urlpatterns = [
    path("favicon.ico", favicon_ico),
    path("manifest.webmanifest", manifest),
    path("search/", SearchView.as_view(), name="search"),
    path("sw.js", service_worker),
    path("offline/", offline),
    path("brand/<str:name>", brand_file),
    path("assets/app.<str:version>.css", app_css),
    path("admin/", admin.site.urls),
    path("befui/<path:name>", befui.asset),
    path("api/v1/leads/<str:token>/", LeadWebhookView.as_view(), name="lead_webhook"),
    path("api/", include("apps.ingestion.urls")),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.dsr.api_urls")),
    path("api/serop/", include("apps.serop.urls")),
    path("products/", include("apps.products.urls")),
    path("errors/", include("apps.errors.urls")),
    path("tickets/", include("apps.tickets.urls")),
    path("automation/", include("apps.automation.urls")),
    path("feedback/", include("apps.feedback.urls")),
    path("leads/", include("apps.leads.urls")),
    path("dashboards/", include("apps.dashboards.urls")),
    # Historic singular path, kept alive for old bookmarks and anything that
    # hardcoded it. A redirect, not a second `include`: including the same
    # module twice registers the `dashboards` namespace twice (urls.W005) and
    # makes reverse() ambiguous about which prefix it will produce.
    path("dashboard/", RedirectView.as_view(pattern_name="dashboards:index")),
    path("dsr/", include("apps.dsr.urls")),
    path("attendance/", include("apps.attendance.urls")),
    path("leave/", include("apps.leave.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("costing/", include("apps.costing.urls")),
    path("payroll/", include("apps.payroll.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("presence/", include("apps.presence.urls")),
    path("", include("apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

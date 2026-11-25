from django.urls import path

from apps.appauth import cards_web, quality_web, web

app_name = "appauth_web"

urlpatterns = [
    path("", web.UsersView.as_view(), name="users"),
    path("export.csv", web.ExportView.as_view(), name="export"),
    path("scan-quality/", quality_web.ScanQualityView.as_view(), name="scan_quality"),
    path("scan-quality/export.csv", quality_web.ScanQualityExportView.as_view(), name="scan_quality_export"),
    path("cards/export.csv", cards_web.CardsExportView.as_view(), name="cards_export"),
    path("cards/", cards_web.CardsView.as_view(), name="cards"),
    path("cards/<uuid:pk>/", cards_web.CardDetailView.as_view(), name="card"),
    path("<uuid:pk>/", web.UserDetailView.as_view(), name="detail"),
    path("<uuid:pk>/<str:action>/", web.UserActionView.as_view(), name="action"),
]

from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.ListView.as_view(), name="list"),
    path("feed/", views.FeedView.as_view(), name="feed"),
    path("read-all/", views.MarkAllReadView.as_view(), name="read_all"),
    path("<int:pk>/open/", views.OpenView.as_view(), name="open"),
    path("push/subscribe/", views.PushSubscribeView.as_view(), name="push_subscribe"),
    path("push/unsubscribe/", views.PushUnsubscribeView.as_view(), name="push_unsubscribe"),
]

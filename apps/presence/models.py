from django.conf import settings
from django.db import models

from apps.core.models import TenantScopedModel


class PresenceSession(TenantScopedModel):
    """One open browser tab connected to /ws/presence/.

    A row per connection, not per user: a person with three tabs open is online
    until the last one closes, and a tab that dies without saying goodbye is
    dropped by `last_seen` going stale instead of leaving a count that never
    gets decremented.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="presence_sessions",
    )
    channel_name = models.CharField(max_length=255, unique=True)
    path = models.CharField(max_length=255, blank=True, default="")
    activity = models.CharField(max_length=120, blank=True, default="")
    # False while the tab is hidden or the person has been idle for a while.
    is_active = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta(TenantScopedModel.Meta):
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.user_id} @ {self.path}"

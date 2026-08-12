from django.conf import settings
from django.db import models
from django.utils import timezone


class DSREntry(models.Model):
    class Category(models.TextChoices):
        TICKET = "ticket", "Ticket Completion"
        BUG_FIX = "bug_fix", "Bug Fix"
        FEATURE = "feature", "Feature Development"
        CODE_REVIEW = "code_review", "Code Review"
        MEETING = "meeting", "Meeting / Sync"
        DOCUMENTATION = "documentation", "Documentation"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        IN_PROGRESS = "in_progress", "In Progress"
        BLOCKED = "blocked", "Blocked"

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="dsr_entries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dsr_entries",
    )
    date = models.DateField(default=timezone.localdate)

    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dsr_entries",
    )
    task_name = models.CharField(max_length=255)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.TICKET,
    )

    created_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)
    hours_spent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    notes = models.TextField(blank=True)
    is_auto_logged = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-completed_time", "-created_at"]
        verbose_name = "DSR Entry"
        verbose_name_plural = "DSR Entries"

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.task_name}"

    @property
    def time_taken_formatted(self):
        if self.created_time and self.completed_time:
            delta = self.completed_time - self.created_time
            total_seconds = max(0, int(delta.total_seconds()))
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        elif self.hours_spent > 0:
            total_minutes = int(float(self.hours_spent) * 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "N/A"

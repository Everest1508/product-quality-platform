from django.contrib import admin

from apps.tickets.models import Ticket, TicketAttachment, TicketComment


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("pk", "title", "status", "priority", "ticket_type", "assigned_to", "created_at")
    list_filter = ("status", "priority", "ticket_type", "source")
    search_fields = ("title", "description")
    raw_id_fields = ("created_by", "assigned_to", "linked_error_group")


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author", "created_at")
    raw_id_fields = ("ticket", "author")


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ("file_name", "ticket", "file_size", "uploaded_by", "created_at")
    raw_id_fields = ("ticket", "uploaded_by")

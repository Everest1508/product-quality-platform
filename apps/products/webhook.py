import json
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


def send_discord_webhook(webhook_url, embed):
    if not webhook_url:
        return
    webhook_url = webhook_url.strip()
    payload = {"embeds": [embed]}
    data = json.dumps(payload).encode("utf-8")
    req = Request(webhook_url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "PQ-Platform/1.0")
    try:
        resp = urlopen(req, timeout=5)
        return resp.status == 204
    except URLError as e:
        logger.warning("Discord webhook failed: %s", e)
        return False


def notify_ticket_created(ticket):
    product = ticket.product
    if not product or not product.discord_webhook_url:
        return
    fields = [
        {"name": "Title", "value": ticket.title, "inline": False},
        {"name": "Type", "value": ticket.get_ticket_type_display(), "inline": True},
        {"name": "Priority", "value": ticket.get_priority_display(), "inline": True},
        {"name": "Status", "value": ticket.get_status_display(), "inline": True},
    ]
    if ticket.created_by:
        fields.append({"name": "Created by", "value": ticket.created_by.get_full_name() or ticket.created_by.username, "inline": True})
    if ticket.assigned_to:
        fields.append({"name": "Assigned to", "value": ticket.assigned_to.get_full_name() or ticket.assigned_to.username, "inline": True})
    embed = {
        "title": f"Ticket #{ticket.pk} Created",
        "color": 0x5865F2,
        "fields": fields,
        "timestamp": ticket.created_at.isoformat(),
    }
    send_discord_webhook(product.discord_webhook_url, embed)


def notify_ticket_status_changed(ticket, old_status):
    product = ticket.product
    if not product or not product.discord_webhook_url:
        return
    embed = {
        "title": f"Ticket #{ticket.pk} Status Changed",
        "color": 0xFEE75C,
        "fields": [
            {"name": "Title", "value": ticket.title, "inline": False},
            {"name": "Old Status", "value": old_status, "inline": True},
            {"name": "New Status", "value": ticket.get_status_display(), "inline": True},
        ],
        "timestamp": ticket.updated_at.isoformat(),
    }
    send_discord_webhook(product.discord_webhook_url, embed)


def notify_ticket_assigned(ticket):
    product = ticket.product
    if not product or not product.discord_webhook_url:
        return
    embed = {
        "title": f"Ticket #{ticket.pk} Assigned",
        "color": 0x57F287,
        "fields": [
            {"name": "Title", "value": ticket.title, "inline": False},
            {"name": "Assigned to", "value": ticket.assigned_to.get_full_name() or ticket.assigned_to.username if ticket.assigned_to else "Nobody", "inline": True},
            {"name": "Status", "value": ticket.get_status_display(), "inline": True},
        ],
        "timestamp": ticket.updated_at.isoformat(),
    }
    send_discord_webhook(product.discord_webhook_url, embed)


def notify_error_captured(error_group, occurrence):
    product = error_group.product
    if not product or not product.discord_webhook_url:
        return
    embed = {
        "title": f"Error Captured: {error_group.title[:80]}",
        "color": 0xED4245,
        "fields": [
            {"name": "Error Type", "value": error_group.error_type or "N/A", "inline": True},
            {"name": "Environment", "value": occurrence.environment, "inline": True},
            {"name": "Severity", "value": error_group.severity, "inline": True},
            {"name": "Occurrences", "value": str(error_group.occurrence_count), "inline": True},
            {"name": "Page", "value": occurrence.page if occurrence.page else "N/A", "inline": True},
        ],
        "timestamp": occurrence.created_at.isoformat(),
    }
    send_discord_webhook(product.discord_webhook_url, embed)


def notify_feedback_created(feedback):
    product = feedback.product
    if not product or not product.discord_webhook_url:
        return
    embed = {
        "title": f"Feedback Received ({feedback.rating}/5)",
        "color": 0x9B59B6,
        "fields": [
            {"name": "Rating", "value": f"{'⭐' * feedback.rating}", "inline": True},
            {"name": "User", "value": feedback.user_ref or "Anonymous", "inline": True},
            {"name": "Product", "value": product.name, "inline": True},
        ],
        "timestamp": feedback.created_at.isoformat(),
    }
    if feedback.comment:
        embed["fields"].append({"name": "Comment", "value": feedback.comment[:500], "inline": False})
    send_discord_webhook(product.discord_webhook_url, embed)

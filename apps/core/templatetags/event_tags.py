from django import template

register = template.Library()

_EVENT_PILLS = {
    "ticket_created": "open",
    "auto_ticket": "open",
    "ticket_assigned": "assigned",
    "ticket_status_changed": "progress",
    "ticket_resolved": "resolved",
    "ticket_commented": "info",
    "ticket_deleted": "critical",
    "error_captured": "critical",
    "error_created": "critical",
    "error_status_changed": "progress",
    "error_resolved": "resolved",
    "error_ignored": "closed",
    "error_deleted": "critical",
    "feedback_received": "csat",
    "survey_response": "nps",
    "survey_created": "active",
    "survey_toggled": "progress",
    "survey_deleted": "closed",
    "member_joined": "active",
    "member_removed": "closed",
    "member_role_changed": "progress",
    "product_created": "active",
    "product_updated": "progress",
    "product_deleted": "closed",
    "api_key_created": "active",
    "api_key_revoked": "closed",
    "version_added": "active",
    "version_removed": "closed",
    "access_granted": "active",
    "access_revoked": "closed",
    "rule_created": "active",
    "rule_updated": "progress",
    "rule_deleted": "closed",
    "rule_toggled": "progress",
}


@register.filter
def event_pill(event_type):
    return _EVENT_PILLS.get(event_type, "info")


@register.filter
def event_label(event_type):
    from apps.dashboards.models import ActivityLog
    return dict(ActivityLog.EventType.choices).get(event_type, event_type)

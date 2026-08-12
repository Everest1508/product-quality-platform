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


@register.filter
def event_url(entry):
    if not entry:
        return ""

    from django.urls import reverse

    try:
        et = getattr(entry, "event_type", "") or ""
        ct = getattr(entry, "target_content_type", "") or ""
        oid = getattr(entry, "target_object_id", None)
        meta = getattr(entry, "metadata", {}) or {}
        pid = meta.get("product_id") if isinstance(meta, dict) else None

        # Errors
        if et.startswith("error_") or ct in ("error", "error_group"):
            if oid and et != "error_deleted":
                return reverse("errors:error_detail", kwargs={"pk": oid})
            if pid:
                return reverse("products:product_errors", kwargs={"pk": pid})
            return reverse("errors:error_list")

        # Tickets
        if et.startswith("ticket_") or et == "auto_ticket" or ct == "ticket":
            if oid and et != "ticket_deleted":
                return reverse("tickets:ticket_detail", kwargs={"pk": oid})
            return reverse("tickets:ticket_board")

        # Surveys & Feedback
        if et.startswith("survey_") or et == "feedback_received" or ct == "survey":
            if oid and et != "survey_deleted":
                return reverse("feedback:survey_detail", kwargs={"pk": oid})
            return reverse("feedback:cs_hub")

        # Products & Product-scoped items
        if et.startswith("product_") or et.startswith("version_") or et.startswith("api_key_") or et.startswith("access_") or et.startswith("rule_") or ct == "product":
            target_pk = pid or (oid if ct == "product" else None)
            if target_pk and et != "product_deleted":
                return reverse("products:product_detail", kwargs={"pk": target_pk})
            return reverse("products:product_list")

        # Team / Membership
        if et.startswith("member_") or ct == "membership":
            return reverse("accounts:team_list")

    except Exception:
        pass

    return ""

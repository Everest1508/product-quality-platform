"""Automation rule actions with their side effects (activity log), shared by the JSON API.
Access checks stay with the caller."""

from apps.automation.forms import AutoTicketRuleForm
from apps.dashboards.service import log_activity


def create_rule(data, actor, company, user=None, product=None):
    """Returns (rule, form); rule is None when invalid. `product` fixes the product on a product page."""
    data = dict(data)
    if product is not None:
        data["product"] = product.pk
    form = AutoTicketRuleForm(data, company=company, user=user)
    if not form.is_valid():
        return None, form
    rule = form.save(commit=False)
    rule.company = company
    rule.save()
    log_activity(company, "rule_created", f"Rule '{rule.name}' created", actor=actor,
                 target_content_type="rule", target_object_id=rule.pk, metadata={"product_id": rule.product_id})
    return rule, form


def update_rule(data, rule, actor, company, user=None):
    form = AutoTicketRuleForm(data, instance=rule, company=company, user=user)
    if not form.is_valid():
        return None, form
    form.save()
    log_activity(company, "rule_updated", f"Rule '{rule.name}' updated", actor=actor,
                 target_content_type="rule", target_object_id=rule.pk, metadata={"product_id": rule.product_id})
    return rule, form


def delete_rule(rule, actor, company):
    name, pk, product_id = rule.name, rule.pk, rule.product_id
    rule.delete()
    log_activity(company, "rule_deleted", f"Rule '{name}' deleted", actor=actor,
                 target_content_type="rule", target_object_id=pk, metadata={"product_id": product_id})
    return name


def toggle_rule(rule, actor, company):
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active"])
    state = "enabled" if rule.is_active else "disabled"
    log_activity(company, "rule_toggled", f"Rule '{rule.name}' {state}", actor=actor,
                 target_content_type="rule", target_object_id=rule.pk,
                 metadata={"product_id": rule.product_id, "is_active": rule.is_active})
    return state

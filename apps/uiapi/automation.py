from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.automation import service
from apps.automation.models import AutoTicketLog, AutoTicketRule
from apps.products.access import accessible_products
from apps.uiapi.tickets import form_errors, scoped_product
from apps.uiapi.views import CompanyAPIView

PER_PAGE = 25
SORTS = {"created": "created_at", "-created": "-created_at", "name": "name", "-name": "-name", "fired": "-trigger_count", "-fired": "trigger_count"}
User = get_user_model()


def _is_admin(request):
    return request.company_role in ("owner", "admin")


def _rules(request):
    """Rules on products the user can open, plus company-wide rules for owners and admins:
    a company-wide rule acts on every product, so it is theirs to manage."""
    q = Q(product__in=accessible_products(request.user, request.company))
    if _is_admin(request):
        q |= Q(product__isnull=True)
    return AutoTicketRule.objects.filter(company=request.company).filter(q)


def _rule(request, pk):
    return get_object_or_404(_rules(request).select_related("product", "assign_to"), pk=pk)


def rule_json(r):
    return {
        "id": r.pk, "name": r.name,
        "product": {"id": r.product_id, "name": r.product.name} if r.product_id else None,
        "trigger_type": r.trigger_type, "severity": r.severity, "threshold_count": r.threshold_count,
        "window_minutes": r.window_minutes, "action": r.action, "action_label": r.get_action_display(),
        "assign_to": r.assign_to_id, "is_active": r.is_active, "trigger_count": r.trigger_count,
        "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
    }


def _guard_company_wide(request, data_product):
    if not data_product and not _is_admin(request):
        raise PermissionDenied("Only owners and admins can make a rule for every product.")


class RuleListAPIView(CompanyAPIView):
    def get(self, request):
        q = request.query_params
        product = scoped_product(request)
        qs = product.auto_ticket_rules.all() if product else _rules(request)
        qs = qs.select_related("product", "assign_to")
        if q.get("q", "").strip():
            qs = qs.filter(name__icontains=q["q"].strip())
        if q.get("trigger"):
            qs = qs.filter(trigger_type=q["trigger"])
        if q.get("active") in ("0", "1"):
            qs = qs.filter(is_active=q["active"] == "1")
        page = Paginator(qs.order_by(SORTS.get(q.get("sort", ""), "-created_at")), PER_PAGE).get_page(q.get("page", 1))
        logs = []
        if not product:
            rule_ids = _rules(request).values("pk")
            logs = [
                {"id": l.pk, "rule": l.rule.name, "action": l.action_taken, "matched": l.matched_count,
                 "created_at": l.created_at.isoformat(),
                 "ticket": {"key": l.ticket.key, "id": l.ticket_id} if l.ticket_id else None}
                for l in AutoTicketLog.objects.filter(company=request.company, rule__in=rule_ids)
                .select_related("rule", "ticket", "ticket__product")[:10]
            ]
        return Response({
            "items": [rule_json(r) for r in page],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
            "recent_logs": logs,
        })

    def post(self, request):
        product = scoped_product(request)
        _guard_company_wide(request, product or request.data.get("product"))
        rule, form = service.create_rule(request.data, request.user, request.company, user=request.user, product=product)
        if rule is None:
            return Response(form_errors(form), status=400)
        return Response({"id": rule.pk, "message": f"Rule '{rule.name}' created."}, status=201)


class RuleMetaAPIView(CompanyAPIView):
    def get(self, request):
        product = scoped_product(request)
        members = User.objects.filter(memberships__company=request.company).order_by("username")
        return Response({
            "products": [] if product else [{"id": p.pk, "name": p.name} for p in accessible_products(request.user, request.company).order_by("name")],
            "members": [{"id": u.pk, "name": u.get_full_name() or u.username} for u in members],
            "triggers": [list(c) for c in AutoTicketRule.TriggerType.choices],
            "actions": [list(c) for c in AutoTicketRule.ActionType.choices],
            "severities": [["", "All severities"], ["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]],
            "can_company_wide": _is_admin(request),
        })


class RuleDetailAPIView(CompanyAPIView):
    def get(self, request, pk):
        return Response({"rule": rule_json(_rule(request, pk))})

    def patch(self, request, pk):
        rule = _rule(request, pk)
        _guard_company_wide(request, request.data.get("product"))
        saved, form = service.update_rule(request.data, rule, request.user, request.company, user=request.user)
        if saved is None:
            return Response(form_errors(form), status=400)
        return Response({"rule": rule_json(AutoTicketRule.objects.select_related("product", "assign_to").get(pk=saved.pk)), "message": f"Rule '{saved.name}' updated."})

    def delete(self, request, pk):
        rule = _rule(request, pk)
        return Response({"deleted": service.delete_rule(rule, request.user, request.company)})


class RuleToggleAPIView(CompanyAPIView):
    def post(self, request, pk):
        rule = _rule(request, pk)
        state = service.toggle_rule(rule, request.user, request.company)
        return Response({"rule": rule_json(rule), "message": f"Rule '{rule.name}' {state}."})

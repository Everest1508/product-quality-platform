from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.feedback import service
from apps.feedback.models import SentimentRecord, Survey, SurveyResponse
from apps.products.access import accessible_products, require_product_access
from apps.uiapi.tickets import form_errors, scoped_product
from apps.uiapi.views import CompanyAPIView

PER_PAGE = 25
SORTS = {
    "created": "created_at", "-created": "-created_at", "name": "name", "-name": "-name",
    "responses": "response_count", "-responses": "-response_count",
}


def _surveys(request):
    """Surveys of products the user can open, in this company."""
    return Survey.objects.filter(company=request.company, product__in=accessible_products(request.user, request.company))


def _survey(request, pk):
    survey = get_object_or_404(_surveys(request).select_related("product", "created_by"), pk=pk)
    return survey


def survey_json(s):
    return {
        "id": s.pk, "name": s.name, "description": s.description, "type": s.survey_type,
        "type_label": s.get_survey_type_display(), "status": s.status, "status_label": s.get_status_display(),
        "product": {"id": s.product_id, "name": s.product.name},
        "response_count": s.response_count, "created_at": s.created_at.isoformat(),
        "url": f"/feedback/{s.pk}/",
    }


def survey_detail_json(request, s, **extra):
    s = Survey.objects.select_related("product", "created_by").get(pk=s.pk)
    responses = list(s.responses.all()[:50])
    dist = dict(s.responses.values_list("score").annotate(n=Count("pk")).order_by())
    return {
        "survey": {
            **survey_json(s),
            "created_by": (s.created_by.get_full_name() or s.created_by.username) if s.created_by_id else "",
            "public_path": f"/feedback/respond/{s.pk}/",
            "avg_score": s.compute_avg_score(),
            "nps": s.compute_nps(),
        },
        "distribution": [{"score": n, "count": dist.get(n, 0), "label": s.score_label(n)} for n in s.score_range()],
        "responses": [
            {"id": r.pk, "score": r.score, "label": s.score_label(r.score), "comment": r.comment,
             "contact_name": r.contact_name, "created_at": r.created_at.isoformat()}
            for r in responses
        ],
        **extra,
    }


class SurveyListAPIView(CompanyAPIView):
    def get(self, request):
        q = request.query_params
        product = scoped_product(request)
        qs = product.surveys.all() if product else _surveys(request)
        qs = qs.select_related("product", "created_by")
        if q.get("status"):
            qs = qs.filter(status=q["status"])
        if q.get("type"):
            qs = qs.filter(survey_type=q["type"])
        if q.get("q", "").strip():
            qs = qs.filter(name__icontains=q["q"].strip())
        sort = q.get("sort", "-created")
        if "responses" in sort:
            qs = qs.annotate(response_count_n=Count("responses"))
            order = ("-" if sort.startswith("-") else "") + "response_count_n"
        else:
            order = SORTS.get(sort, "-created_at")
        page = Paginator(qs.order_by(order), PER_PAGE).get_page(q.get("page", 1))
        return Response({
            "items": [survey_json(s) for s in page],
            "page": {"number": page.number, "num_pages": page.paginator.num_pages, "count": page.paginator.count, "per_page": PER_PAGE},
        })

    def post(self, request):
        """Create a survey. The product is the page's product, or the body's, and must be one the user can open."""
        product = scoped_product(request)
        survey, form = service.create_survey(request.data, request.user, request.company, user=request.user, product=product)
        if survey is None:
            return Response(form_errors(form), status=400)
        return Response({"id": survey.pk, "url": f"/feedback/{survey.pk}/", "message": f"Survey '{survey.name}' created."}, status=201)


class SurveyMetaAPIView(CompanyAPIView):
    def get(self, request):
        product = scoped_product(request)
        return Response({
            "types": [list(c) for c in Survey.SurveyType.choices],
            "statuses": [list(c) for c in Survey.Status.choices],
            "products": [] if product else [
                {"id": p.pk, "name": p.name} for p in accessible_products(request.user, request.company).order_by("name")
            ],
        })


class SurveyDetailAPIView(CompanyAPIView):
    def get(self, request, pk):
        return Response(survey_detail_json(request, _survey(request, pk)))

    def delete(self, request, pk):
        survey = _survey(request, pk)
        return Response({"deleted": service.delete_survey(survey, request.user, request.company)})


class SurveyToggleAPIView(CompanyAPIView):
    def post(self, request, pk):
        survey = _survey(request, pk)
        service.toggle_survey(survey, request.user, request.company)
        return Response(survey_detail_json(request, survey, message=f"Survey status changed to '{survey.get_status_display()}'."))


class CsHubAPIView(CompanyAPIView):
    def get(self, request):
        company = request.company
        products = list(accessible_products(request.user, company))
        surveys = Survey.objects.filter(company=company, product__in=products).select_related("product")
        responses = SurveyResponse.objects.filter(company=company, survey__product__in=products)
        sentiment = list(
            SentimentRecord.objects.filter(company=company, product__in=products).select_related("product").order_by("-recorded_at")[:100]
        )
        avg_all = responses.aggregate(avg=Avg("score"))["avg"]
        per_product = {
            row["survey__product_id"]: row
            for row in responses.values("survey__product_id").annotate(n=Count("pk"), avg=Avg("score"))
        }
        survey_counts = dict(surveys.values_list("product_id").annotate(n=Count("pk")).order_by())
        stats = []
        for p in products:
            row = per_product.get(p.pk)
            stats.append({
                "product": {"id": p.pk, "name": p.name, "slug": p.slug},
                "survey_count": survey_counts.get(p.pk, 0),
                "response_count": row["n"] if row else 0,
                "avg_score": round(row["avg"], 1) if row and row["avg"] else None,
                "dashboard_url": f"/dashboards/product/{p.pk}/",
            })
        active = [survey_json(s) for s in surveys.filter(status="active")]
        return Response({
            "total_responses": responses.count(),
            "avg_all": round(avg_all, 1) if avg_all else None,
            "active_surveys": active,
            "sentiment_total": SentimentRecord.objects.filter(company=company, product__in=products).count(),
            "sentiment": [
                {"id": r.pk, "product": r.product.name, "source": r.source, "score": float(r.score), "recorded_at": str(r.recorded_at)}
                for r in sentiment
            ],
            "product_stats": stats,
        })


class PublicSurveyAPIView(APIView):
    """The page behind a survey's public link. No login: anyone with the link may answer while it is active."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def _survey(self, pk):
        return get_object_or_404(Survey.objects.select_related("product"), pk=pk, status="active")

    def get(self, request, pk):
        s = self._survey(pk)
        return Response({
            "id": s.pk, "name": s.name, "description": s.description, "type": s.survey_type,
            "product": s.product.name, "scores": list(s.score_range()),
        })

    def post(self, request, pk):
        s = self._survey(pk)
        if not hasattr(request.data, "get"):
            return Response({"detail": "Send a JSON object."}, status=400)
        response, form = service.submit_response(s, request.data)
        if response is None:
            return Response(form_errors(form), status=400)
        return Response({"ok": True}, status=201)

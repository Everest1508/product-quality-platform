from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.core.mixins import CompanyMemberRequiredMixin
from apps.feedback.forms import SurveyCreateForm, SurveyResponseForm
from apps.feedback.models import SentimentRecord, Survey, SurveyResponse
from apps.products.models import Product


SURVEY_SORT_MAP = {
    "created": "created_at",
    "-created": "-created_at",
    "name": "name",
    "-name": "-name",
    "responses": "response_count",
    "-responses": "-response_count",
}


class SurveyListView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        qs = Survey.objects.filter(company=request.company).select_related("product", "created_by")

        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        survey_type = request.GET.get("type")
        if survey_type:
            qs = qs.filter(survey_type=survey_type)

        search = request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)

        sort = request.GET.get("sort", "-created")
        order = SURVEY_SORT_MAP.get(sort, "-created_at")
        qs = qs.order_by(order)

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))

        if request.headers.get("HX-Request") == "true":
            return render(request, "feedback/partials/_survey_list_body.html", {
                "page": page,
            })

        return render(request, "feedback/survey_list.html", {
            "page": page,
            "current_status": status,
            "current_type": survey_type,
            "search": search,
            "current_sort": sort,
        })


class SurveyCreateView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        form = SurveyCreateForm(company=request.company)
        return render(request, "feedback/survey_form.html", {"form": form, "editing": False})

    def post(self, request):
        form = SurveyCreateForm(request.POST, company=request.company)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.company = request.company
            survey.created_by = request.user
            survey.save()
            messages.success(request, f"Survey '{survey.name}' created.")
            return redirect("feedback:survey_detail", pk=survey.pk)
        return render(request, "feedback/survey_form.html", {"form": form, "editing": False})


class SurveyDetailView(CompanyMemberRequiredMixin, View):
    def get(self, request, pk):
        survey = get_object_or_404(
            Survey.objects.select_related("product", "created_by"),
            pk=pk,
            company=request.company,
        )
        responses = survey.responses.all()[:50]
        avg_score = survey.compute_avg_score()
        nps_score = survey.compute_nps()
        response_count = survey.response_count

        response_distribution = {}
        for s in survey.score_range():
            count = survey.responses.filter(score=s).count()
            response_distribution[s] = count

        if request.headers.get("HX-Request") == "true":
            return render(request, "feedback/partials/_survey_detail_content.html", {
                "survey": survey,
                "responses": responses,
                "avg_score": avg_score,
                "nps_score": nps_score,
                "response_count": response_count,
                "response_distribution": response_distribution,
            })

        return render(request, "feedback/survey_detail.html", {
            "survey": survey,
            "responses": responses,
            "avg_score": avg_score,
            "nps_score": nps_score,
            "response_count": response_count,
            "response_distribution": response_distribution,
        })


class SurveyToggleView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk, company=request.company)
        if survey.status == "draft":
            survey.status = "active"
        elif survey.status == "active":
            survey.status = "closed"
        else:
            survey.status = "draft"
        survey.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Survey status changed to '{survey.get_status_display()}'.")
        return redirect("feedback:survey_detail", pk=survey.pk)


class SurveyDeleteView(CompanyMemberRequiredMixin, View):
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk, company=request.company)
        name = survey.name
        survey.delete()
        messages.success(request, f"Survey '{name}' deleted.")
        return redirect("feedback:survey_list")


class PublicSurveyView(View):
    def get(self, request, pk):
        survey = get_object_or_404(
            Survey.objects.select_related("product"),
            pk=pk,
            status="active",
        )
        form = SurveyResponseForm(initial={"score": 5})
        return render(request, "feedback/survey/public_survey.html", {
            "survey": survey,
            "form": form,
            "score_range": survey.score_range(),
        })

    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk, status="active")
        form = SurveyResponseForm(request.POST)

        if form.is_valid():
            SurveyResponse.objects.create(
                survey=survey,
                company=survey.company,
                score=form.cleaned_data["score"],
                comment=form.cleaned_data.get("comment", ""),
                contact_name=form.cleaned_data.get("contact_name", ""),
                contact_email=form.cleaned_data.get("contact_email", ""),
            )
            return render(request, "feedback/survey/survey_thankyou.html", {
                "survey": survey,
            })

        return render(request, "feedback/survey/public_survey.html", {
            "survey": survey,
            "form": form,
            "score_range": survey.score_range(),
        })


class CustomerSuccessHubView(CompanyMemberRequiredMixin, View):
    def get(self, request):
        company = request.company
        products = Product.objects.filter(company=company)

        sentiment_records = SentimentRecord.objects.filter(
            company=company
        ).select_related("product").order_by("-recorded_at")

        surveys = Survey.objects.filter(company=company).select_related("product")
        active_surveys = surveys.filter(status="active")
        closed_surveys = surveys.filter(status="closed")

        total_responses = SurveyResponse.objects.filter(company=company).count()
        avg_all = SurveyResponse.objects.filter(company=company).aggregate(avg=Avg("score"))["avg"]

        product_stats = []
        for product in products:
            product_surveys = surveys.filter(product=product)
            product_responses = SurveyResponse.objects.filter(
                survey__product=product
            )
            resp_count = product_responses.count()
            avg = product_responses.aggregate(avg=Avg("score"))["avg"]
            product_stats.append({
                "product": product,
                "survey_count": product_surveys.count(),
                "response_count": resp_count,
                "avg_score": round(avg, 1) if avg else None,
            })

        sentiment_by_product = {}
        for product in products:
            records = sentiment_records.filter(product=product)
            if records.exists():
                sentiment_by_product[product.pk] = [
                    {"date": r.recorded_at.isoformat(), "score": float(r.score), "source": r.source}
                    for r in records[:30]
                ]

        if request.headers.get("HX-Request") == "true":
            return render(request, "feedback/partials/_cs_hub_content.html", {
                "products": products,
                "product_stats": product_stats,
                "active_surveys": active_surveys,
                "sentiment_by_product": sentiment_by_product,
                "total_responses": total_responses,
                "avg_all": round(avg_all, 1) if avg_all else None,
            })

        return render(request, "feedback/cs_hub.html", {
            "products": products,
            "product_stats": product_stats,
            "active_surveys": active_surveys,
            "closed_surveys": closed_surveys,
            "sentiment_records": sentiment_records,
            "sentiment_by_product": sentiment_by_product,
            "total_responses": total_responses,
            "avg_all": round(avg_all, 1) if avg_all else None,
        })

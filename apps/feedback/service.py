"""Survey actions with their side effects (activity log), shared by the JSON API.
Access checks stay with the caller."""

from apps.dashboards.service import log_activity
from apps.feedback.forms import SurveyCreateForm, SurveyResponseForm
from apps.feedback.models import Survey, SurveyResponse


def create_survey(data, actor, company, user=None, product=None):
    """Returns (survey, form); survey is None when the form is invalid. `product`, when given,
    fixes the product (a product page); otherwise the form's product must be one `user` can open."""
    data = dict(data)
    if product is not None:
        data["product"] = product.pk
    form = SurveyCreateForm(data, company=company, user=user)
    if not form.is_valid():
        return None, form
    survey = form.save(commit=False)
    survey.company, survey.created_by = company, actor
    survey.save()
    log_activity(
        company, "survey_created",
        f"Survey '{survey.name}' created for {survey.product.name}" if product is not None else f"Survey '{survey.name}' created",
        actor=actor, target_content_type="survey", target_object_id=survey.pk, metadata={"product_id": survey.product_id},
    )
    return survey, form


def toggle_survey(survey, actor, company):
    """draft → active → closed → draft."""
    survey.status = {"draft": "active", "active": "closed"}.get(survey.status, "draft")
    survey.save(update_fields=["status", "updated_at"])
    log_activity(
        company, "survey_toggled", f"Survey '{survey.name}' status changed", description=survey.get_status_display(),
        actor=actor, target_content_type="survey", target_object_id=survey.pk,
        metadata={"product_id": survey.product_id, "status": survey.status},
    )


def delete_survey(survey, actor, company):
    name, pk = survey.name, survey.pk
    survey.delete()
    log_activity(company, "survey_deleted", f"Survey '{name}' deleted", actor=actor,
                 target_content_type="survey", target_object_id=pk)
    return name


def submit_response(survey, data):
    """The public form. Returns (response, form); response is None when invalid."""
    form = SurveyResponseForm(data)
    if not form.is_valid():
        return None, form
    c = form.cleaned_data
    response = SurveyResponse.objects.create(
        survey=survey, company=survey.company, score=c["score"], comment=c.get("comment", ""),
        contact_name=c.get("contact_name", ""), contact_email=c.get("contact_email", ""),
    )
    log_activity(
        survey.company, "survey_response", f"Survey response received: {response.score}",
        description=f"Response to '{survey.name}'", target_content_type="survey_response", target_object_id=response.pk,
        metadata={"survey_id": survey.pk, "product_id": survey.product_id, "score": response.score},
    )
    return response, form

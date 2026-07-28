from django import forms

from apps.feedback.models import Survey


class SurveyCreateForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ["name", "description", "survey_type", "product", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q1 NPS Survey"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Optional description..."}),
            "survey_type": forms.Select(attrs={"class": "form-input"}),
            "product": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["product"].queryset = company.product_set.all()


class SurveyResponseForm(forms.Form):
    score = forms.IntegerField(
        min_value=0,
        max_value=10,
        widget=forms.NumberInput(attrs={
            "class": "form-input",
            "style": "width:80px;text-align:center;font-size:20px;font-weight:600;",
        }),
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Any additional comments..."}),
    )
    contact_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Your name (optional)"}),
    )
    contact_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "Your email (optional)"}),
    )

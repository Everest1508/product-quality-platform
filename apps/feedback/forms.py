from django import forms

from apps.feedback.models import Survey


class SurveyCreateForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = ["name", "description", "survey_type", "product", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Q1 NPS Survey"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional description..."}),
            "survey_type": forms.Select(attrs={}),
            "product": forms.Select(attrs={}),
            "status": forms.Select(attrs={}),
        }

    def __init__(self, *args, company=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            if user is not None:
                from apps.products.access import accessible_products

                self.fields["product"].queryset = accessible_products(user, company)
            else:
                self.fields["product"].queryset = company.product_set.all()


class SurveyResponseForm(forms.Form):
    score = forms.IntegerField(
        min_value=0,
        max_value=10,
        widget=forms.NumberInput(attrs={
            "style": "width:80px;text-align:center;font-size:20px;font-weight:600;",
        }),
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Any additional comments..."}),
    )
    contact_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Your name (optional)"}),
    )
    contact_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "Your email (optional)"}),
    )

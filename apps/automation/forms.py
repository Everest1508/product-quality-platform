from django import forms

from apps.automation.models import AutoTicketRule


class AutoTicketRuleForm(forms.ModelForm):
    class Meta:
        model = AutoTicketRule
        fields = [
            "name", "product", "trigger_type", "severity",
            "threshold_count", "window_minutes", "action", "assign_to", "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "High error rate on production",
            }),
            "product": forms.Select(attrs={"class": "form-input"}),
            "trigger_type": forms.Select(attrs={"class": "form-input"}),
            "severity": forms.Select(attrs={"class": "form-input"}),
            "threshold_count": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "window_minutes": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "action": forms.Select(attrs={"class": "form-input"}),
            "assign_to": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.products.models import Product
            from django.contrib.auth import get_user_model
            User = get_user_model()
            self.fields["product"].queryset = Product.objects.filter(company=company)
            self.fields["assign_to"].queryset = User.objects.filter(memberships__company=company)
        else:
            self.fields["product"].queryset = AutoTicketRule._meta.get_field("product").remote_field.model.objects.none()
            self.fields["assign_to"].queryset = AutoTicketRule._meta.get_field("assign_to").remote_field.model.objects.none()

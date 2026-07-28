from django import forms

from apps.ingestion.models import ErrorGroup, ErrorOccurrence


class ErrorCreateForm(forms.Form):
    product = forms.ModelChoiceField(queryset=None, widget=forms.HiddenInput())
    title = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Error title"}))
    error_type = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TypeError, ValueError"}))
    severity = forms.ChoiceField(choices=ErrorGroup.SEVERITY_CHOICES, initial="medium", widget=forms.Select(attrs={"class": "form-input"}))
    stacktrace = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "form-input", "rows": 4, "placeholder": "Paste stacktrace here (optional)"}))
    environment = forms.CharField(max_length=20, initial="production", widget=forms.TextInput(attrs={"class": "form-input"}))
    page = forms.CharField(max_length=500, required=False, widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Page URL where error occurred"}))

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.products.models import Product
            self.fields["product"].queryset = Product.objects.filter(company=company)

    def save(self, company, user):
        data = self.cleaned_data
        product = data["product"]
        from apps.ingestion.models import compute_fingerprint
        fingerprint = compute_fingerprint(data["error_type"], data["title"], data.get("stacktrace", ""))

        group, created = ErrorGroup.objects.get_or_create(
            company=company,
            product=product,
            fingerprint=fingerprint,
            defaults={
                "title": data["title"],
                "error_type": data.get("error_type", ""),
                "severity": data.get("severity", "medium"),
                "status": "open",
            },
        )
        if not created:
            group.occurrence_count += 1
            group.save(update_fields=["occurrence_count", "last_seen"])

        ErrorOccurrence.objects.create(
            company=company,
            error_group=group,
            environment=data.get("environment", "production"),
            stacktrace=data.get("stacktrace", ""),
            page=data.get("page", ""),
        )
        return group

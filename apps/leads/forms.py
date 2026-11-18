from django import forms


class LeadForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40, required=False)
    company = forms.CharField(max_length=200, required=False)
    need = forms.CharField(max_length=100, required=False)
    details = forms.CharField(max_length=10000)


class NewLeadForm(forms.Form):
    """A lead typed in by hand. Keys match Lead's field names so cleaned_data goes straight to create()."""

    full_name = forms.CharField(max_length=200, label="client name")
    company_name = forms.CharField(max_length=200, required=False)
    industry = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=40, required=False)
    details = forms.CharField(max_length=10000, label="project info")

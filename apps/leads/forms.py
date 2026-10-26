from django import forms


class LeadForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    company = forms.CharField(max_length=200, required=False)
    need = forms.CharField(max_length=100, required=False)
    details = forms.CharField(max_length=10000)

from django import forms

from apps.tickets.models import Ticket


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "ticket_type", "priority", "product"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Brief summary of the issue",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 5,
                "placeholder": "Detailed description...",
            }),
            "ticket_type": forms.Select(attrs={"class": "form-input"}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "product": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.products.models import Product
            self.fields["product"].queryset = Product.objects.filter(company=company)
        else:
            self.fields["product"].queryset = Ticket._meta.get_field("product").remote_field.model.objects.none()


class TicketEditForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "ticket_type", "priority", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 5}),
            "ticket_type": forms.Select(attrs={"class": "form-input"}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
        }


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Add a comment...",
        }),
    )

from django import forms

from apps.tickets.models import Ticket


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "ticket_type", "priority", "product",
                  "assignees", "deadline"]
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
            "assignees": forms.SelectMultiple(attrs={
                "class": "form-input",
                "size": 6,
            }),
            "deadline": forms.DateTimeInput(attrs={
                "class": "form-input",
                "type": "datetime-local",
            }),
        }

    def __init__(self, *args, company=None, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from django.contrib.auth import get_user_model
            from apps.products.models import Product
            self.fields["product"].queryset = Product.objects.filter(company=company)
            if product:
                from apps.products.access import product_users
                self.fields["assignees"].queryset = product_users(product, company)
            else:
                self.fields["assignees"].queryset = (
                    get_user_model().objects.filter(memberships__company=company).order_by("username")
                )
        else:
            self.fields["product"].queryset = Ticket._meta.get_field("product").remote_field.model.objects.none()
            self.fields["assignees"].queryset = (
                Ticket._meta.get_field("assignees").remote_field.model.objects.none()
            )


class TicketEditForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "description", "ticket_type", "priority", "status",
                  "assignees", "deadline"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 5}),
            "ticket_type": forms.Select(attrs={"class": "form-input"}),
            "priority": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "assignees": forms.SelectMultiple(attrs={
                "class": "form-input",
                "size": 6,
            }),
            "deadline": forms.DateTimeInput(attrs={
                "class": "form-input",
                "type": "datetime-local",
            }),
        }


class TicketDeadlineForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["deadline"]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={
                "class": "form-input",
                "type": "datetime-local",
            }),
        }


class TicketCommentForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Add a comment...",
        }),
    )

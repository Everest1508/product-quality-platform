from django import forms
from django.utils.text import slugify

from apps.products.keys import KEY_RE, MAX_LEN
from apps.products.models import Product, ProductVersion


class TicketKeyMixin:
    """The `key` field: three or four capitals that name the product's tickets.

    Left blank on a new product, it is suggested from the name. It is unique within
    the company because ticket numbers read AUM-001 across every product.
    """

    def clean_key(self):
        key = (self.cleaned_data.get("key") or "").strip().upper()
        if not key:
            return ""
        if not KEY_RE.match(key):
            raise forms.ValidationError(
                f"Use 2 to {MAX_LEN} letters or digits, starting with a letter."
            )
        company = getattr(self, "company", None) or getattr(self.instance, "company", None)
        clash = Product.objects.filter(company=company, key=key).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f"{clash.first().name} already uses {key}.")
        return key


class ProductCreateForm(TicketKeyMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "key", "description", "default_environment", "discord_webhook_url"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "My App",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 3,
                "placeholder": "Optional description",
            }),
            "default_environment": forms.Select(attrs={"class": "form-input"}),
            "discord_webhook_url": forms.URLInput(attrs={
                "class": "form-input",
                "placeholder": "https://discord.com/api/webhooks/...",
            }),
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        slug = slugify(name)
        if not slug:
            raise forms.ValidationError("Could not generate a valid slug.")
        if self.instance.pk is None:
            if Product.objects.filter(company=self.company, slug=slug).exists():
                raise forms.ValidationError("A product with a similar name already exists.")
        return name

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        instance.company = self.company
        if commit:
            instance.save()
        return instance


class ProductEditForm(TicketKeyMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "key", "description", "default_environment", "discord_webhook_url"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "default_environment": forms.Select(attrs={"class": "form-input"}),
        }


class VersionCreateForm(forms.ModelForm):
    class Meta:
        model = ProductVersion
        fields = ["version_string", "is_current"]
        widgets = {
            "version_string": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "1.0.0",
            }),
            "is_current": forms.CheckboxInput(attrs={
                "class": "form-input",
                "style": "width:auto;",
            }),
        }

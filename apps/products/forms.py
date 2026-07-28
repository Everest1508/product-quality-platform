from django import forms
from django.utils.text import slugify

from apps.products.models import Product, ProductVersion


class ProductCreateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "description", "default_environment"]
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


class ProductEditForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "description", "default_environment"]
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

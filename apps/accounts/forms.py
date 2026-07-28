from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from apps.accounts.models import Company, Membership

User = get_user_model()


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        "class": "form-input",
        "placeholder": "you@company.com",
    }))
    first_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "First name",
    }))
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Last name",
    }))

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Username",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Password",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-input",
            "placeholder": "Confirm password",
        })


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Username or email",
        "autofocus": True,
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-input",
        "placeholder": "Password",
    }))


class CompanyCreateForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Acme Corp",
            }),
        }

    def clean_name(self):
        name = self.cleaned_data["name"]
        slug = slugify(name)
        if not slug:
            raise ValidationError("Could not generate a valid slug from this name.")
        if Company.objects.filter(slug=slug).exists():
            raise ValidationError("A company with a similar name already exists.")
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name)
        if commit:
            instance.save()
        return instance


class TeamCreateMemberForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Username",
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "form-input",
        "placeholder": "teammate@company.com",
    }))
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "First name",
    }))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Last name",
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        "class": "form-input",
        "placeholder": "Password",
    }))
    role = forms.ChoiceField(
        choices=[(r.value, r.label) for r in Membership.Role if r.value != "owner"],
        initial="developer",
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
        )
        return Membership.objects.create(
            user=user,
            company=self.company,
            role=self.cleaned_data["role"],
        )


class TeamEditForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "First name",
    }))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={
        "class": "form-input",
        "placeholder": "Last name",
    }))
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        "class": "form-input",
        "placeholder": "Email",
    }))
    role = forms.ChoiceField(
        choices=[(r.value, r.label) for r in Membership.Role if r.value != "owner"],
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.membership = membership
        self.fields["role"].initial = membership.role if membership else "developer"

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        existing = User.objects.filter(email=email).exclude(pk=self.membership.user_id).exists()
        if existing:
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self):
        user = self.membership.user
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
        new_role = self.cleaned_data["role"]
        if self.membership.role != new_role:
            self.membership.role = new_role
            self.membership.save(update_fields=["role"])
        return self.membership


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-input",
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-input",
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-input",
            }),
        }

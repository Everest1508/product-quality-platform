from decimal import Decimal

from django import forms

from apps.payroll.models import Holiday, PayrollProfile

MAX_DAILY_RATE = Decimal("1000000.00")
MAX_MONTHLY_SALARY = Decimal("100000000.00")


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ["date", "name"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Diwali, Christmas…"}
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_date(self):
        value = self.cleaned_data["date"]
        existing = Holiday.objects.filter(company=self.company, date=value)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("That date is already a holiday.")
        return value

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip() or "Holiday"


class PayrollProfileForm(forms.ModelForm):
    """A monthly salary, which is what payroll divides into a day rate.

    ``daily_rate`` stays on the model as the fallback for anyone paid by the
    day, so it is still accepted here, but a salary is the intended input and
    the screen only asks for that.
    """

    class Meta:
        model = PayrollProfile
        fields = [
            "monthly_salary",
            "daily_rate",
            "currency",
            "effective_from",
            "is_on_payroll",
            "notes",
        ]
        widgets = {
            "monthly_salary": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            "daily_rate": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0"}
            ),
            # No inline width: the setup screen sizes this with .aux, and an
            # inline style would win and blow out the column.
            "currency": forms.TextInput(attrs={"class": "form-input", "maxlength": 8}),
            "effective_from": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}
            ),
            "is_on_payroll": forms.CheckboxInput(),
            "notes": forms.TextInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, user=None, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.company = company
        self.fields["effective_from"].label = "Effective from"
        # Currency is not worth a column of its own on the setup screen, so it is
        # never required in the POST: fall back to whatever the profile already
        # says, then to INR. A hand-rolled or older client that omits it entirely
        # must still save.
        if self.instance and self.instance.pk and self.instance.currency:
            self.fields["currency"].initial = self.instance.currency
        self.fields["currency"].required = False
        self.fields["monthly_salary"].label = "Monthly salary"
        # Optional on the form, but one of the two has to end up filled in,
        # which clean() is there to insist on.
        self.fields["monthly_salary"].required = False
        self.fields["daily_rate"].required = False

    def clean(self):
        cleaned = super().clean()
        monthly = cleaned.get("monthly_salary")
        rate = cleaned.get("daily_rate")

        if monthly is not None and monthly > 0:
            if monthly > MAX_MONTHLY_SALARY:
                self.add_error("monthly_salary", "That salary looks wrong.")
            # The day rate is recomputed per cycle; never store a derived value.
            cleaned["daily_rate"] = Decimal("0.00")
        elif rate is None or rate <= 0:
            self.add_error("monthly_salary", "Enter a monthly salary.")

        return cleaned

    def clean_monthly_salary(self):
        value = self.cleaned_data.get("monthly_salary")
        if value is not None and value < 0:
            raise forms.ValidationError("A salary cannot be negative.")
        return value

    def clean_daily_rate(self):
        rate = self.cleaned_data.get("daily_rate")
        if rate is None:
            return rate
        if rate < 0:
            raise forms.ValidationError("A rate cannot be negative.")
        if rate > MAX_DAILY_RATE:
            raise forms.ValidationError("That rate looks wrong.")
        return rate.quantize(Decimal("0.01"))

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "INR").strip().upper()[:8]

    def clean_effective_from(self):
        return self.cleaned_data["effective_from"]


class CycleForm(forms.Form):
    """Which pay cycle to show. Defaults to the cycle running today."""

    anchor = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )

    def clean_anchor(self):
        return self.cleaned_data.get("anchor")

from decimal import Decimal

from django import forms

from apps.products.models import Product
from apps.dsr.duration import MESSAGE, format_hm, parse_hours
from apps.dsr.models import DSREntry

MAX_HOURS = Decimal("24")

HOUR_CHOICES = [(str(i), f"{i} hr") for i in range(0, 25)]
MINUTE_CHOICES = [(str(i), f"{i} min") for i in range(0, 60, 5)]


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Product.__str__ is "Company / Product", which repeats the company in a
        # list that only ever holds one company's products.
        return obj.name


class DSREntryForm(forms.ModelForm):
    """Manual DSR entry.

    Hours are capped per entry so one row cannot silently swallow a whole
    week's reporting, and the task name is required because an unnamed row
    is useless in a timesheet.
    """

    # Not required at the field level, so clean_task_name can give a useful
    # message instead of the bare "This field is required." Declaring the field
    # here overrides Meta.widgets, so the widget must be repeated.
    task_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "What did you work on?"}
        ),
    )

    hours = forms.ChoiceField(
        choices=HOUR_CHOICES,
        required=False,
        initial="0",
        widget=forms.Select(attrs={"class": "form-input dc-time-select"}),
    )

    minutes = forms.ChoiceField(
        choices=MINUTE_CHOICES,
        required=False,
        initial="0",
        widget=forms.Select(attrs={"class": "form-input dc-time-select"}),
    )

    product = ProductChoiceField(
        queryset=Product.objects.none(),
        required=False,
        empty_label="No product",
        widget=forms.Select(attrs={"class": "form-input"}),
    )

    def __init__(self, *args, id_prefix="dsr-add", products=None, **kwargs):
        """Stamp widget ids so two forms can share a page.

        The sheet renders the "log it" form twice -- once in the bar above the
        table and once in the table's empty state -- so a plain `DSREntryForm()`
        put the same `id` on the page twice, which is invalid HTML and makes
        `label[for]` ambiguous. Setting `id` on the widget stops Django's
        auto_id from overriding it, so each instance is addressable.
        """
        super().__init__(*args, **kwargs)
        # Only products the person can open, so a posted id for anything else is
        # an invalid choice rather than a way to tag work against a product they
        # cannot see. Without a list the field offers nothing.
        if products is not None:
            self.fields["product"].queryset = products

        # Override the DecimalField with a CharField so text values like "45m"
        # reach clean() without being rejected by the Decimal validator.
        self.fields["hours_spent"] = forms.CharField(
            required=False, widget=forms.HiddenInput()
        )

        for name, field in self.fields.items():
            field.widget.attrs["id"] = f"{id_prefix}-{name}"

    class Meta:
        model = DSREntry
        fields = ["task_name", "product", "category", "hours_spent", "status", "notes"]
        widgets = {
            "hours_spent": forms.HiddenInput(),
            "category": forms.Select(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-input"}),
            "notes": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Optional note"}
            ),
        }

    def clean_task_name(self):
        name = (self.cleaned_data.get("task_name") or "").strip()
        if not name:
            raise forms.ValidationError("Describe the task.")
        return name

    def clean(self):
        cleaned = super().clean()
        # Path 1: dropdowns (add-entry form)
        h = int(cleaned.get("hours") or 0)
        m = int(cleaned.get("minutes") or 0)
        if h or m:
            total = Decimal(h) + Decimal(m) / 60
            changed = True
        else:
            # Path 2: raw hours_spent text (inline row edit, API)
            raw = self.data.get("hours_spent", "")
            if raw:
                try:
                    total = parse_hours(str(raw))
                except ValueError:
                    self.add_error("hours", MESSAGE)
                    return cleaned
                # Only treat as changed if the value differs from the instance.
                # This prevents re-capping a wide entry the user did not touch.
                if self.instance and self.instance.pk:
                    changed = total != self.instance.hours_spent
                else:
                    changed = True
            else:
                total = None
                changed = False
        if total is not None:
            if total <= 0:
                self.add_error("hours", "Log more than zero hours.")
            elif changed and total > MAX_HOURS:
                self.add_error("hours", f"Cannot exceed {MAX_HOURS} hours.")
            cleaned["hours_spent"] = total.quantize(Decimal("0.01"))
        else:
            cleaned["hours_spent"] = Decimal("0.00")
        return cleaned
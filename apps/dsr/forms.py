from decimal import Decimal

from django import forms

from apps.products.models import Product
from apps.dsr.duration import MESSAGE, format_hm, parse_hours
from apps.dsr.models import DSREntry

MAX_HOURS = Decimal("24")


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Product.__str__ is "Company / Product", which repeats the company in a
        # list that only ever holds one company's products.
        return obj.name


class HoursField(forms.CharField):
    """Time typed as `1.5`, `45m` or `1h 30m`; cleans to hours as a Decimal."""

    def prepare_value(self, value):
        # Show a stored number the way people read it, so the box round-trips.
        return format_hm(value) if isinstance(value, (Decimal, int, float)) else value

    def to_python(self, value):
        value = super().to_python(value)
        try:
            return parse_hours(value)
        except ValueError:
            raise forms.ValidationError(MESSAGE)

    def has_changed(self, initial, data):
        try:
            return parse_hours(data) != parse_hours(initial if initial is not None else "")
        except ValueError:
            return True


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

    hours_spent = HoursField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "1h 30m", "inputmode": "text", "autocomplete": "off"}
        ),
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
        for name, field in self.fields.items():
            field.widget.attrs["id"] = f"{id_prefix}-{name}"

    class Meta:
        model = DSREntry
        fields = ["task_name", "product", "category", "hours_spent", "status", "notes"]
        widgets = {
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

    def clean_hours_spent(self):
        hours = self.cleaned_data.get("hours_spent")
        if hours is None:
            return Decimal("0.00")
        if hours <= 0:
            raise forms.ValidationError("Log more than zero hours.")
        if "hours_spent" in self.changed_data and hours > MAX_HOURS:
            raise forms.ValidationError(f"A single entry cannot exceed {MAX_HOURS} hours.")
        return hours
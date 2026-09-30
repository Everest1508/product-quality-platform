from decimal import Decimal

from django import forms

from apps.dsr.models import DSREntry

MAX_HOURS = Decimal("24")


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

    def __init__(self, *args, id_prefix="dsr-add", **kwargs):
        """Stamp widget ids so two forms can share a page.

        The sheet renders the "log it" form twice -- once in the bar above the
        table and once in the table's empty state -- so a plain `DSREntryForm()`
        put the same `id` on the page twice, which is invalid HTML and makes
        `label[for]` ambiguous. Setting `id` on the widget stops Django's
        auto_id from overriding it, so each instance is addressable.
        """
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["id"] = f"{id_prefix}-{name}"

    class Meta:
        model = DSREntry
        fields = ["task_name", "category", "hours_spent", "status", "notes"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-input"}),
            "hours_spent": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.25", "min": "0", "max": str(MAX_HOURS)}
            ),
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
        if hours > MAX_HOURS:
            raise forms.ValidationError(f"A single entry cannot exceed {MAX_HOURS} hours.")
        return hours
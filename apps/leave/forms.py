from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.icons import ICON_CHOICES, ICON_NAMES, render_icon
from apps.leave import service
from apps.leave.models import LeavePolicy, LeaveRequest


class LeaveRequestForm(forms.Form):
    """Apply for leave.

    ``days`` is computed rather than typed in, so what gets charged always
    matches the range the person asked for.
    """

    policy_id = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs={"class": "form-input"}),
        label="Leave type",
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        required=False,
    )
    is_half_day = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(),
        label="Half day",
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 3}),
    )

    def __init__(self, *args, company=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.user = user
        self.fields["policy_id"].choices = [
            (str(p.pk), p.name) for p in service.policies_for(company)
        ]
        today = timezone.localdate()
        self.fields["start_date"].widget.attrs["min"] = today.isoformat()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("policy_id"):
            return cleaned

        policy = service.get_policy(self.company, cleaned["policy_id"])
        if policy is None:
            self.add_error("policy_id", "That leave type is not available here.")
            return cleaned

        start = cleaned.get("start_date")
        end = cleaned.get("end_date") or start
        cleaned["end_date"] = end

        try:
            cleaned["days"] = service.validate_request(
                self.company,
                self.user,
                policy,
                start,
                end,
                cleaned.get("is_half_day", False),
            )
        except forms.ValidationError as exc:
            self.add_error(None, exc)

        cleaned["policy"] = policy
        return cleaned

    def save(self, user):
        cleaned = self.cleaned_data
        return LeaveRequest.objects.create(
            company=self.company,
            user=user,
            policy=cleaned["policy"],
            start_date=cleaned["start_date"],
            end_date=cleaned["end_date"],
            is_half_day=cleaned.get("is_half_day", False),
            days=cleaned["days"],
            reason=cleaned.get("reason", "").strip(),
            status=LeaveRequest.Status.PENDING,
        )


class LeavePolicyForm(forms.ModelForm):
    """Set the per-type allowance and spell cap. Blank means unlimited."""

    max_days_per_year = forms.DecimalField(
        required=False,
        decimal_places=1,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "placeholder": "Unlimited"}
        ),
    )
    max_consecutive_days = forms.DecimalField(
        required=False,
        decimal_places=1,
        min_value=Decimal("0.5"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "placeholder": "Unlimited"}
        ),
    )

    class Meta:
        model = LeavePolicy
        fields = [
            "name",
            "max_days_per_year",
            "max_consecutive_days",
            "is_paid",
            "color",
            "icon",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "is_paid": forms.CheckboxInput(),
            "color": forms.Select(
                attrs={"class": "form-input lp-colour"}
            ),
            "icon": forms.Select(
                attrs={"class": "form-input lp-icon-select"}
            ),
        }

    def clean_color(self):
        """Reject anything that is not a known token.

        The value is interpolated into a CSS class name, so a free-text colour
        here is a style-injection vector (`url(...)`, quotes, braces). Only the
        closed set in `LeavePolicy.COLOR_TOKENS` is stored.
        """
        token = (self.cleaned_data.get("color") or "").strip().lower()
        if token and token not in LeavePolicy.COLOR_NAMES:
            raise ValidationError(
                "Pick one of the listed colours."
            )
        return token

    def clean_icon(self):
        """Same closed-set rule as `clean_color`, for the same reason."""
        name = (self.cleaned_data.get("icon") or "").strip()
        if name and name not in ICON_NAMES:
            raise ValidationError("Pick one of the listed icons.")
        return name

    def clean_max_days_per_year(self):
        return self.cleaned_data.get("max_days_per_year") or None

    def clean_max_consecutive_days(self):
        return self.cleaned_data.get("max_consecutive_days") or None

    def clean(self):
        cleaned = super().clean()
        annual = cleaned.get("max_days_per_year")
        consecutive = cleaned.get("max_consecutive_days")
        if annual is not None and consecutive is not None and consecutive > annual:
            self.add_error(
                "max_consecutive_days",
                "A single spell cannot be longer than the annual allowance.",
            )
        return cleaned
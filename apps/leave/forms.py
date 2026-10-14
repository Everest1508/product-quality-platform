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

    # The four `id`s the apply screen names in its `hx-include` list, set here
    # rather than in the template so the ids the htmx wiring depends on and the
    # ones Django renders cannot drift apart. A renamed field would otherwise
    # leave the preview silently posting three of four inputs and pricing the
    # wrong span.
    policy_id = forms.ChoiceField(
        choices=(),
        widget=forms.Select(
            attrs={"class": "form-input", "id": "apply-policy"}
        ),
        label="Leave type",
    )
    start_date = forms.DateField(
        widget=forms.DateInput(
            attrs={"class": "form-input", "type": "date", "id": "apply-start"}
        ),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(
            attrs={"class": "form-input", "type": "date", "id": "apply-end"}
        ),
        required=False,
    )
    is_half_day = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"id": "apply-half"}),
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
            result = service.validate_and_split(
                self.company,
                self.user,
                policy,
                start,
                end,
                cleaned.get("is_half_day", False),
            )
        except forms.ValidationError as exc:
            self.add_error(None, exc)
        else:
            cleaned["days"] = result["days"]
            cleaned["paid_days"] = result["paid"]
            cleaned["unpaid_days"] = result["unpaid"]
            cleaned["split_reasons"] = result["reasons"]

        cleaned["policy"] = policy
        return cleaned

    def split_summary(self):
        """What this application will cost, for the live preview under the form.

        Reads `cleaned_data`, so it is only meaningful after `is_valid()`; the
        template guards on form.is_valid() before asking.
        """
        cleaned = self.cleaned_data
        paid = cleaned.get("paid_days")
        if paid is None:
            return ""
        unpaid = cleaned.get("unpaid_days") or Decimal("0.0")
        parts = []
        if paid > 0:
            parts.append(f"{service.format_days(paid)} paid")
        if unpaid > 0:
            parts.append(f"{service.format_days(unpaid)} unpaid")
        return " · ".join(parts)

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
            # The applicant's split is the automatic one, computed once here so
            # the approver sees a definite number to argue with. Only an
            # approver's decision (LeaveDecisionForm) writes `manual`.
            paid_days=cleaned.get("paid_days"),
            unpaid_days=cleaned.get("unpaid_days"),
            split_mode=LeaveRequest.SplitMode.AUTO,
            reason=cleaned.get("reason", "").strip(),
            status=LeaveRequest.Status.PENDING,
        )


class LeaveDecisionForm(forms.Form):
    """Approve or reject, with the approver's call on paid vs unpaid.

    The dates are editable because "approve 3 of the 5 days they asked for" is a
    real decision and forcing an approver to reject-and-reapply for it wastes
    everybody's day. Editing them re-validates the shortened span from scratch
    (overlap, weekend-only, past) rather than trusting the original application,
    since a shorter span can invalidate rules the longer one passed.
    """

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    is_half_day = forms.BooleanField(required=False, widget=forms.CheckboxInput())
    split_mode = forms.ChoiceField(
        choices=LeaveRequest.SplitMode.choices,
        widget=forms.RadioSelect(attrs={"class": "form-split-mode"}),
        initial=LeaveRequest.SplitMode.AUTO,
    )
    paid_days = forms.DecimalField(
        required=False,
        decimal_places=1,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "min": "0"}
        ),
    )
    unpaid_days = forms.DecimalField(
        required=False,
        decimal_places=1,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "min": "0"}
        ),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 2}),
    )

    def __init__(self, *args, company=None, leave=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.leave = leave
        if leave is not None:
            self.fields["start_date"].initial = leave.start_date
            self.fields["end_date"].initial = leave.end_date
            self.fields["is_half_day"].initial = leave.is_half_day
            self.fields["split_mode"].initial = leave.split_mode
            self.fields["paid_days"].initial = leave.split["paid"]
            self.fields["unpaid_days"].initial = leave.split["unpaid"]

    def clean(self):
        cleaned = super().clean()
        if self.leave is None:
            return cleaned

        start = cleaned.get("start_date")
        end = cleaned.get("end_date") or start
        if not start:
            return cleaned
        cleaned["end_date"] = end

        try:
            result = service.validate_and_split(
                self.company,
                self.leave.user,
                self.leave.policy,
                start,
                end,
                cleaned.get("is_half_day", False),
                exclude_pk=self.leave.pk,
            )
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            return cleaned

        cleaned["days"] = result["days"]
        cleaned["auto_paid"] = result["paid"]
        cleaned["auto_unpaid"] = result["unpaid"]
        try:
            split = service.resolve_split(
                self.company,
                self.leave.user,
                self.leave.policy,
                start,
                end,
                result["days"],
                cleaned.get("split_mode") or LeaveRequest.SplitMode.AUTO,
                cleaned.get("paid_days"),
                cleaned.get("unpaid_days"),
                exclude_pk=self.leave.pk,
            )
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            return cleaned

        cleaned["paid_days"] = split["paid"]
        cleaned["unpaid_days"] = split["unpaid"]
        return cleaned


class LeavePolicyForm(forms.ModelForm):
    """Set the per-type paid allowance and paid spell cap. Blank means no cap.

    Neither box stops anybody booking leave any more; both cap how many days
    are *paid*, and the excess is charged unpaid. A blank is "no cap" for that
    one limit, and the two are independent -- either may be set alone. The one
    combination refused is a spell cap *above* the annual allowance, which
    could never be reached; see `clean`.
    """

    # The labels name what the number caps -- *paid* days -- because that is
    # what changed. They are also what the invalid-save toast prints
    # (`_report_errors`), so they have to read as a sentence there, not as
    # "max_days_per_year".
    max_days_per_year = forms.DecimalField(
        required=False,
        label="Paid days per year",
        decimal_places=1,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "placeholder": "No cap"}
        ),
    )
    max_consecutive_days = forms.DecimalField(
        required=False,
        label="Paid days per spell",
        decimal_places=1,
        min_value=Decimal("0.5"),
        widget=forms.NumberInput(
            attrs={"class": "form-input", "step": "0.5", "placeholder": "No cap"}
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
        """A paid spell cap above the paid annual allowance is refused.

        It is not a contradiction to *have* both limits -- either can be blank,
        and either can bind on its own -- but a spell cap above the annual
        allowance can never be reached: the allowance binds first, so every
        request past the year is unpaid regardless. That is dead configuration.

        It used to be allowed, and the form's answer was to keep the *old*
        value for the field and report success, so an admin who typed 5 got 3
        back and no message explaining why. A silent discard is worse than a
        refusal, so this refuses.
        """
        cleaned = super().clean()
        annual = cleaned.get("max_days_per_year")
        spell = cleaned.get("max_consecutive_days")
        if annual is not None and spell is not None and spell > annual:
            self.add_error(
                "max_consecutive_days",
                "The paid days per spell cannot be more than the paid days per "
                "year -- the annual allowance would always bind first. Lower it, "
                "or leave it blank for no spell limit.",
            )
        return cleaned
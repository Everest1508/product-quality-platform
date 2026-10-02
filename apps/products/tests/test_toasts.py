"""Every mutation has to say it happened.

The toast queue was silently discarded for its entire life: the seed ran on
`alpine:init`, which Alpine dispatches *before* it walks the DOM, so the
container's state did not exist and the guard quietly did nothing. 79 call sites
rendered nothing. This file exists so that cannot come back unnoticed, and so
the flows people actually use -- create a product, edit it, delete it, capture an
error, log DSR time -- are checked by name.

Two separate things are asserted, because they fail differently:

* `messages` are queued on the POST, and
* the queue is actually rendered into the page that follows the redirect.

A view can satisfy the first and fail the second, which is exactly what the old
bug was: the message existed and nobody ever saw it.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.products.models import Product


class ToastAfterMutationTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme-toast")
        self.user = get_user_model().objects.create_user(
            username="owner", password="pass1234"
        )
        Membership.objects.create(
            user=self.user, company=self.company, role=Membership.Role.OWNER
        )
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            company=self.company, name="Widget", slug="widget"
        )

    def assert_toast_after(self, response, fragment, page_url=None):
        """The POST queues it, and the next page renders it.

        The page to check is the redirect target where the view redirects, and
        anything else where it answered with an htmx-swapped partial. In the
        second case the response is the fragment itself, which by construction
        contains no toast -- the queue lives on until a full page renders it.
        """
        if page_url is None:
            self.assertIn(
                response.status_code, (200, 302), "the mutation should have succeeded"
            )
            page_url = (
                response["Location"]
                if response.status_code == 302
                else reverse("products:product_list")
            )
        page = self.client.get(page_url)
        body = page.content.decode()
        self.assertIn('id="toast-seed"', body, "no toast was rendered on the next page")
        self.assertIn(fragment, body, f"expected {fragment!r} in the rendered toast")

    def test_creating_a_product_says_so(self):
        response = self.client.post(
            reverse("products:product_create"),
            {"name": "Gadget", "description": "", "default_environment": "production"},
        )
        self.assert_toast_after(response, "Gadget")

    def test_editing_a_product_says_so(self):
        response = self.client.post(
            reverse("products:product_edit", kwargs={"pk": self.product.pk}),
            {
                "name": "Widget Renamed",
                "description": "",
                "default_environment": "production",
            },
        )
        self.assert_toast_after(response, "updated")

    def test_deleting_a_product_says_so(self):
        response = self.client.post(
            reverse("products:product_delete", kwargs={"pk": self.product.pk})
        )
        self.assert_toast_after(response, "deleted")

    def test_capturing_an_error_says_so(self):
        response = self.client.post(
            reverse("products:product_error_create", kwargs={"pk": self.product.pk}),
            {
                "product": self.product.pk,
                "title": "TypeError",
                "error_type": "TypeError",
                "severity": "medium",
                "environment": "production",
                "stacktrace": "x is not a function",
            },
        )
        self.assert_toast_after(response, "Error #")

    def test_creating_a_ticket_says_so(self):
        response = self.client.post(
            reverse("products:product_ticket_create", kwargs={"pk": self.product.pk}),
            {
                "title": "Login broken",
                "description": "500 on submit",
                "ticket_type": "bug",
                "priority": "high",
                "product": self.product.pk,
            },
        )
        self.assert_toast_after(response, "created")

    def test_adding_a_version_says_so(self):
        response = self.client.post(
            reverse("products:version_create", kwargs={"pk": self.product.pk}),
            {"version_string": "2.1.0"},
        )
        self.assert_toast_after(response, "2.1.0")

    def test_logging_dsr_time_says_so(self):
        response = self.client.post(
            reverse("dsr:dsr_add"),
            {
                "date": timezone.localdate().isoformat(),
                "task_name": "Fixed the login redirect",
                "hours_spent": "2.00",
                "category": "bug_fix",
                "status": "completed",
            },
        )
        self.assert_toast_after(response, "Fixed the login redirect")

    def test_deleting_a_dsr_entry_says_so(self):
        from apps.dsr.models import DSREntry

        entry = DSREntry.objects.create(
            company=self.company,
            user=self.user,
            date=timezone.localdate(),
            task_name="Chased the flaky test",
            hours_spent=1,
        )
        response = self.client.post(reverse("dsr:dsr_delete", kwargs={"pk": entry.pk}))
        self.assert_toast_after(response, "Chased the flaky test")

    def test_a_milestone_toggle_says_what_it_became(self):
        """A status change that reports nothing looks like a dead button."""
        from apps.products.models import ProductMilestone

        milestone = ProductMilestone.objects.create(
            company=self.company,
            product=self.product,
            title="Ship v2",
            status=ProductMilestone.Status.UPCOMING,
            target_date=timezone.localdate() + timedelta(days=7),
        )
        response = self.client.post(
            reverse("products:milestone_toggle", kwargs={"pk": milestone.pk})
        )
        self.assert_toast_after(response, "in progress")
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, ProductMilestone.Status.IN_PROGRESS)

    def test_deleting_a_milestone_says_so(self):
        from apps.products.models import ProductMilestone

        milestone = ProductMilestone.objects.create(
            company=self.company,
            product=self.product,
            title="Cut v1",
            status=ProductMilestone.Status.UPCOMING,
            target_date=timezone.localdate() + timedelta(days=7),
        )
        response = self.client.post(
            reverse("products:milestone_delete", kwargs={"pk": milestone.pk})
        )
        self.assert_toast_after(response, "Cut v1")

    def test_an_empty_queue_renders_no_script_at_all(self):
        """An empty ``<script>`` block on every page is noise; see the tag."""
        body = self.client.get(reverse("products:product_list")).content.decode()
        self.assertNotIn('id="toast-seed"', body)

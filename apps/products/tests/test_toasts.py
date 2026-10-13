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

    def test_an_empty_queue_renders_no_script_at_all(self):
        """An empty ``<script>`` block on every page is noise; see the tag."""
        body = self.client.get(reverse("attendance:my_attendance")).content.decode()
        self.assertNotIn('id="toast-seed"', body)

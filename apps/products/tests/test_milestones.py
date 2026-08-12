from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Company, Membership
from apps.products.models import Product, ProductMilestone

User = get_user_model()


class ProductMilestoneTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme Corp", slug="acme")
        self.user = User.objects.create_user(username="admin", password="password")
        Membership.objects.create(user=self.user, company=self.company, role=Membership.Role.OWNER)

        self.product = Product.objects.create(company=self.company, name="Web Platform", slug="web-platform")

    def test_create_milestone_and_status(self):
        m1 = ProductMilestone.objects.create(
            company=self.company,
            product=self.product,
            title="Phase 1: MVP Release",
            target_date=timezone.localdate(),
            order=1,
            status=ProductMilestone.Status.UPCOMING,
        )
        self.assertEqual(m1.computed_status, "upcoming")

        m1.status = ProductMilestone.Status.COMPLETED
        m1.save()
        self.assertEqual(m1.computed_status, "completed")

    def test_milestone_add_and_toggle_views(self):
        self.client.login(username="admin", password="password")
        
        # Add milestone
        add_url = reverse("products:milestone_add", kwargs={"pk": self.product.pk})
        response = self.client.post(add_url, {
            "title": "Phase 2: Beta Launch",
            "target_date": (timezone.localdate() + timedelta(days=7)).isoformat(),
            "order": "2",
        })
        self.assertEqual(response.status_code, 302)

        milestone = ProductMilestone.objects.get(product=self.product, title="Phase 2: Beta Launch")
        self.assertEqual(milestone.order, 2)

        # Toggle status
        toggle_url = reverse("products:milestone_toggle", kwargs={"pk": milestone.pk})
        self.client.post(toggle_url)
        milestone.refresh_from_db()
        self.assertEqual(milestone.status, "in_progress")

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

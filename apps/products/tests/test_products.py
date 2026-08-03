from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import Company, Membership
from apps.products.models import APIKey, Product, ProductVersion

User = get_user_model()


class ProductCRUDTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.client.login(username="alice", password="pass1234")

    def test_product_list_empty(self):
        response = self.client.get(reverse("products:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 0)

    def test_create_product(self):
        response = self.client.post(reverse("products:product_create"), {
            "name": "My App",
            "description": "Test",
            "default_environment": "production",
        })
        self.assertRedirects(response, reverse("products:product_detail", kwargs={"pk": 1}))
        self.assertTrue(Product.objects.filter(slug="my-app", company=self.company).exists())

    def test_product_detail(self):
        product = Product.objects.create(name="Test", slug="test", company=self.company)
        response = self.client.get(reverse("products:product_detail", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product"], product)

    def test_edit_product(self):
        product = Product.objects.create(name="Old", slug="old", company=self.company)
        response = self.client.post(reverse("products:product_edit", kwargs={"pk": product.pk}), {
            "name": "New Name",
            "description": "Updated",
            "default_environment": "staging",
        })
        product.refresh_from_db()
        self.assertEqual(product.name, "New Name")

    def test_delete_product(self):
        product = Product.objects.create(name="Doomed", slug="doomed", company=self.company)
        response = self.client.post(reverse("products:product_delete", kwargs={"pk": product.pk}))
        self.assertRedirects(response, reverse("products:product_list"))
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())


class ProductAdminOnlyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "owner@test.com", "pass1234")
        self.member = User.objects.create_user("dev", "dev@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.owner, company=self.company, role="owner")
        Membership.objects.create(user=self.member, company=self.company, role="developer")

    def test_non_admin_cannot_create_product(self):
        self.client.login(username="dev", password="pass1234")
        response = self.client.get(reverse("products:product_create"))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse("products:product_create"), {
            "name": "Hax",
            "default_environment": "production",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Product.objects.count(), 0)

    def test_non_admin_cannot_edit_product(self):
        product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="dev", password="pass1234")
        response = self.client.post(reverse("products:product_edit", kwargs={"pk": product.pk}), {
            "name": "Hacked",
            "default_environment": "production",
        })
        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.name, "App")

    def test_non_admin_cannot_delete_product(self):
        product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="dev", password="pass1234")
        response = self.client.post(reverse("products:product_delete", kwargs={"pk": product.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

    def test_owner_can_create_product(self):
        self.client.login(username="owner", password="pass1234")
        response = self.client.post(reverse("products:product_create"), {
            "name": "My App",
            "default_environment": "production",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(slug="my-app", company=self.company).exists())


class APIKeyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_create_api_key(self):
        response = self.client.post(
            reverse("products:api_key_create", kwargs={"pk": self.product.pk}),
            {"name": "test-key"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.api_keys.count(), 1)

    def test_revoke_api_key(self):
        api_key, _ = APIKey.create_key(product=self.product, name="to-revoke")
        response = self.client.post(
            reverse("products:api_key_revoke", kwargs={"pk": api_key.pk}),
        )
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)
        self.assertIsNotNone(api_key.revoked_at)


class ProductVersionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("alice", "alice@test.com", "pass1234")
        self.company = Company.objects.create(name="Acme", slug="acme")
        Membership.objects.create(user=self.user, company=self.company, role="owner")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        self.client.login(username="alice", password="pass1234")

    def test_add_version(self):
        response = self.client.post(
            reverse("products:version_create", kwargs={"pk": self.product.pk}),
            {"version_string": "1.0.0", "is_current": True},
        )
        self.assertEqual(ProductVersion.objects.count(), 1)
        v = ProductVersion.objects.first()
        self.assertTrue(v.is_current)


class CrossTenantProductTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_a = User.objects.create_user("alice", "a@test.com", "pass1234")
        self.user_b = User.objects.create_user("bob", "b@test.com", "pass1234")
        self.company_a = Company.objects.create(name="A", slug="a")
        self.company_b = Company.objects.create(name="B", slug="b")
        Membership.objects.create(user=self.user_a, company=self.company_a, role="owner")
        Membership.objects.create(user=self.user_b, company=self.company_b, role="owner")
        self.product_b = Product.objects.create(name="B-App", slug="b-app", company=self.company_b)
        self.client.login(username="alice", password="pass1234")

    def test_cannot_see_other_company_product(self):
        response = self.client.get(reverse("products:product_detail", kwargs={"pk": self.product_b.pk}))
        self.assertEqual(response.status_code, 404)

    def test_product_list_isolation(self):
        Product.objects.create(name="A-App", slug="a-app", company=self.company_a)
        response = self.client.get(reverse("products:product_list"))
        products = response.context["products"]
        self.assertEqual(products.count(), 1)
        self.assertEqual(products.first().company, self.company_a)

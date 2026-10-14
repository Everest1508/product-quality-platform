from django.test import TestCase


class CSHubProductScopeTest(TestCase):
    def test_member_only_sees_products_they_were_added_to(self):
        from apps.accounts.models import Company, Membership, User
        from apps.products.models import Product, ProductAccess

        company = Company.objects.create(name="Acme", slug="acme")
        dev = User.objects.create_user("dev", "d@t.com", "pass1234")
        Membership.objects.create(user=dev, company=company, role="developer")
        mine = Product.objects.create(name="Mine", slug="mine", company=company)
        Product.objects.create(name="Hidden", slug="hidden", company=company)
        ProductAccess.objects.create(user=dev, product=mine, company=company)
        self.client.login(username="dev", password="pass1234")
        s = self.client.session
        s["active_company_id"] = company.pk
        s.save()
        response = self.client.get("/feedback/cs-hub/")
        self.assertEqual([p.name for p in response.context["products"]], ["Mine"])

from apps.uiapi.test_tickets import Base


class ProductNavApiTest(Base):
    def test_counts_urls_and_switcher(self):
        self.make(self.p_open)
        self.make(self.p_open, status="resolved")
        self.login("dev")
        data = self.client.get(f"/ui-api/v1/products/{self.p_open.pk}/nav/").json()
        self.assertEqual(data["name"], "Open")
        self.assertEqual(data["counts"]["tickets"], 1)  # resolved is not open
        self.assertEqual(data["urls"]["tickets"], f"/products/{self.p_open.pk}/tickets/")
        self.assertEqual([p["name"] for p in data["products"]], ["Open"])  # dev cannot open "Hidden"
        self.assertEqual(data["all_url"], "/products/")

    def test_inaccessible_or_foreign_products_are_404(self):
        self.login("dev")
        self.assertEqual(self.client.get(f"/ui-api/v1/products/{self.p_hidden.pk}/nav/").status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(f"/ui-api/v1/products/{self.p_foreign.pk}/nav/").status_code, 404)

    def test_anonymous_is_403(self):
        from django.test import Client

        self.assertEqual(Client().get(f"/ui-api/v1/products/{self.p_open.pk}/nav/").status_code, 403)

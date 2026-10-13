from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.uiapi.test_products_pages import P


class ProductShellPagesTest(P):
    def urls(self):
        pk = self.p_open.pk
        return ["/products/", "/products/create/", f"/products/{pk}/", f"/products/{pk}/edit/", f"/products/{pk}/api/"]

    def test_pages_serve_the_shell_for_admins(self):
        self.login("owner")
        for url in self.urls():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)
            self.assertTemplateNotUsed(r, "core/base.html", msg_prefix=url)

    def test_create_and_edit_stay_admin_only_and_the_rest_is_for_members(self):
        self.login("dev")
        pk = self.p_open.pk
        self.assertEqual(self.client.get("/products/create/").status_code, 403)
        self.assertEqual(self.client.get(f"/products/{pk}/edit/").status_code, 403)
        for url in ("/products/", f"/products/{pk}/", f"/products/{pk}/api/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_no_access_and_foreign_are_404(self):
        self.login("dev")
        self.assertEqual(self.client.get(f"/products/{self.p_hidden.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/products/{self.p_hidden.pk}/api/").status_code, 404)
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_foreign.pk}/").status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        for url in self.urls():
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_url_names_and_removed_routes(self):
        pk = self.p_open.pk
        self.assertEqual(reverse("products:product_list"), "/products/")
        self.assertEqual(reverse("products:product_api", args=[pk]), f"/products/{pk}/api/")
        for name, args in [("product_delete", [1]), ("api_key_create", [1]), ("api_key_rotate", [1]), ("version_create", [1]),
                           ("product_access_add", [1]), ("milestone_toggle", [1]), ("product_key_suggest", [])]:
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(f"products:{name}", args=args)

    def test_old_templates_are_gone(self):
        for name in ["products/product_list.html", "products/product_detail.html", "products/product_form.html", "products/product_api.html",
                     "products/partials/_milestone_tree.html", "products/partials/_api_key_row.html", "products/partials/_product_list_body.html"]:
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(name)

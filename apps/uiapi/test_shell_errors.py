from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.uiapi.test_errors import ErrorsBase


class ErrorShellPagesTest(ErrorsBase):
    def setUp(self):
        super().setUp()
        self.g = self.err(self.p_open)
        self.hidden = self.err(self.p_hidden, "h")

    def urls(self):
        pk = self.p_open.pk
        return ["/errors/", "/errors/create/", f"/errors/{self.g.pk}/",
                f"/products/{pk}/errors/", f"/products/{pk}/errors/create/", f"/products/{pk}/errors/{self.g.pk}/"]

    def test_all_six_urls_serve_the_shell(self):
        self.login("owner")
        for url in self.urls():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)
            self.assertTemplateNotUsed(r, "core/base.html", msg_prefix=url)

    def test_url_names_still_reverse(self):
        pk = self.p_open.pk
        self.assertEqual(reverse("errors:error_list"), "/errors/")
        self.assertEqual(reverse("errors:error_create"), "/errors/create/")
        self.assertEqual(reverse("errors:error_detail", args=[7]), "/errors/7/")
        self.assertEqual(reverse("products:product_errors", args=[pk]), f"/products/{pk}/errors/")
        self.assertEqual(reverse("products:product_error_create", args=[pk]), f"/products/{pk}/errors/create/")
        self.assertEqual(reverse("products:product_error_detail", args=[pk, 7]), f"/products/{pk}/errors/7/")

    def test_no_access_is_404_before_any_shell(self):
        self.login("dev")
        hp = self.p_hidden.pk
        for url in (f"/errors/{self.hidden.pk}/", f"/products/{hp}/errors/", f"/products/{hp}/errors/create/",
                    f"/products/{hp}/errors/{self.hidden.pk}/"):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_an_error_under_the_wrong_product_is_404(self):
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_hidden.pk}/errors/{self.g.pk}/").status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        for url in self.urls():
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_old_templates_and_routes_are_gone(self):
        for name in ["errors/error_list.html", "errors/error_detail.html", "errors/error_form.html",
                     "errors/partials/_error_list_body.html", "errors/partials/_trend_chart.html",
                     "products/product_error_list.html", "products/product_error_detail.html",
                     "products/product_error_form.html", "products/partials/_product_error_list_body.html"]:
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(name)
        for name, args in [("errors:error_status", [1]), ("errors:error_delete", [1]),
                           ("errors:error_convert_to_ticket", [1]), ("products:product_error_convert_to_ticket", [1, 1])]:
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(name, args=args)

    def test_the_dashboard_buttons_still_post(self):
        self.login("owner")
        self.assertEqual(self.client.post(reverse("errors:error_resolve", args=[self.g.pk])).status_code, 302)
        self.g.refresh_from_db()
        self.assertEqual(self.g.status, "resolved")

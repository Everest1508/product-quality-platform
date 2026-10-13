from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.uiapi.test_tickets import Base


class TicketPageShellTest(Base):
    def pages(self, t):
        pk = self.p_open.pk
        return [
            f"/tickets/{t.pk}/", f"/tickets/{t.pk}/edit/", "/tickets/create/",
            f"/products/{pk}/tickets/{t.pk}/", f"/products/{pk}/tickets/create/",
        ]

    def test_all_five_urls_serve_the_shell(self):
        t = self.make(self.p_open)
        self.login("owner")
        for url in self.pages(t):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)
            self.assertTemplateNotUsed(r, "core/base.html", msg_prefix=url)

    def test_url_names_still_reverse_to_the_same_paths(self):
        pk = self.p_open.pk
        self.assertEqual(reverse("tickets:ticket_detail", kwargs={"pk": 7}), "/tickets/7/")
        self.assertEqual(reverse("tickets:ticket_edit", kwargs={"pk": 7}), "/tickets/7/edit/")
        self.assertEqual(reverse("tickets:ticket_create"), "/tickets/create/")
        self.assertEqual(reverse("products:product_ticket_detail", kwargs={"pk": pk, "ticket_pk": 7}), f"/products/{pk}/tickets/7/")
        self.assertEqual(reverse("products:product_ticket_create", kwargs={"pk": pk}), f"/products/{pk}/tickets/create/")

    def test_inaccessible_tickets_and_products_are_404_before_the_shell(self):
        hidden = self.make(self.p_hidden)
        self.login("dev")
        for url in (
            f"/tickets/{hidden.pk}/", f"/tickets/{hidden.pk}/edit/",
            f"/products/{self.p_hidden.pk}/tickets/{hidden.pk}/", f"/products/{self.p_hidden.pk}/tickets/create/",
        ):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_a_product_url_with_another_products_ticket_is_404(self):
        other = self.make(self.p_hidden)
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_open.pk}/tickets/{other.pk}/").status_code, 404)

    def test_another_companys_ticket_is_404(self):
        t = self.make(self.p_foreign)
        self.login("owner")
        self.assertEqual(self.client.get(f"/tickets/{t.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/tickets/{t.pk}/edit/").status_code, 404)

    def test_anonymous_goes_to_login(self):
        t = self.make(self.p_open)
        for url in self.pages(t):
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_legacy_templates_and_routes_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template

        for name in [
            "tickets/ticket_detail.html", "tickets/ticket_form.html",
            "products/product_ticket_detail.html", "products/product_ticket_form.html",
            "tickets/partials/_comment_form.html", "tickets/partials/_comment_list.html",
        ]:
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(name)
        for name in ["ticket_priority", "ticket_deadline", "ticket_follow", "ticket_comment", "ticket_delete"]:
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(f"tickets:{name}", kwargs={"pk": 1})

    def test_old_form_posts_to_the_page_urls_are_not_accepted_any_more(self):
        self.login("owner")
        self.assertEqual(self.client.post("/tickets/create/", {"title": "x"}).status_code, 405)


class LegacyTicketRoutesGoneTest(TicketPageShellTest):
    def test_the_old_status_and_assign_routes_are_gone(self):
        from django.urls import NoReverseMatch, reverse

        for name in ("tickets:ticket_status", "tickets:ticket_assign"):
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(name, args=[1])

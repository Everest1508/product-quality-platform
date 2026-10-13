from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.uiapi.test_tickets import Base


class TicketShellPagesTest(Base):
    def urls(self):
        pk = self.p_open.pk
        return [
            "/tickets/", "/tickets/kanban/", "/tickets/list/",
            f"/products/{pk}/tickets/", f"/products/{pk}/tickets/kanban/", f"/products/{pk}/tickets/list/",
        ]

    def test_all_six_urls_serve_the_shell_for_members(self):
        self.login("owner")
        for url in self.urls():
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTemplateUsed(r, "uiapi/shell.html", msg_prefix=url)
            self.assertTemplateNotUsed(r, "core/base.html", msg_prefix=url)

    def test_url_names_still_reverse_to_the_same_paths(self):
        pk = self.p_open.pk
        self.assertEqual(reverse("tickets:ticket_board"), "/tickets/")
        self.assertEqual(reverse("tickets:ticket_kanban"), "/tickets/kanban/")
        self.assertEqual(reverse("tickets:ticket_list"), "/tickets/list/")
        self.assertEqual(reverse("products:product_board", kwargs={"pk": pk}), f"/products/{pk}/tickets/")
        self.assertEqual(reverse("products:product_ticket_kanban", kwargs={"pk": pk}), f"/products/{pk}/tickets/kanban/")
        self.assertEqual(reverse("products:product_tickets", kwargs={"pk": pk}), f"/products/{pk}/tickets/list/")

    def test_product_pages_404_without_access_before_any_shell_is_served(self):
        self.login("dev")
        for suffix in ("", "kanban/", "list/"):
            self.assertEqual(self.client.get(f"/products/{self.p_hidden.pk}/tickets/{suffix}").status_code, 404, suffix)

    def test_a_product_from_another_company_is_404(self):
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_foreign.pk}/tickets/").status_code, 404)

    def test_anonymous_is_sent_to_login(self):
        for url in self.urls():
            self.assertEqual(Client().get(url).status_code, 302, url)

    def test_old_templates_are_gone(self):
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template

        for name in [
            "tickets/ticket_kanban.html", "tickets/ticket_list.html",
            "products/product_ticket_kanban.html", "products/product_ticket_list.html",
            "tickets/partials/_kanban_columns.html", "tickets/partials/_ticket_list_results.html",
            "tickets/partials/_ticket_filter_bar.html", "tickets/partials/_kanban_drag.html",
            "products/partials/_product_kanban_columns.html", "products/partials/_product_ticket_list_results.html",
        ]:
            with self.assertRaises(TemplateDoesNotExist, msg=name):
                get_template(name)

    def test_the_legacy_bulk_delete_routes_are_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse("tickets:ticket_bulk_delete")
        with self.assertRaises(NoReverseMatch):
            reverse("products:product_ticket_bulk_delete", kwargs={"pk": self.p_open.pk})

    def test_the_ticket_page_is_served_and_deleting_through_the_api_works(self):
        t = self.make(self.p_open, created_by=self.owner)
        self.login("owner")
        self.assertEqual(self.client.get(f"/products/{self.p_open.pk}/tickets/{t.pk}/").status_code, 200)
        self.assertEqual(self.client.delete(f"/ui-api/v1/tickets/{t.pk}/").json(), {"deleted": t.key})
        self.assertEqual(self.client.get(f"/products/{self.p_open.pk}/tickets/{t.pk}/").status_code, 404)

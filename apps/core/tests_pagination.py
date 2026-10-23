from django.test import RequestFactory, SimpleTestCase

from apps.core.pagination import DEFAULT_PAGE_SIZE, paginate


class PaginateTest(SimpleTestCase):
    def size(self, query):
        request = RequestFactory().get("/", query)
        return paginate(request, list(range(150))).paginator.per_page

    def test_allowed_sizes_are_used(self):
        for n in (10, 20, 50, 100):
            self.assertEqual(self.size({"per_page": n}), n)

    def test_anything_else_falls_back_to_default(self):
        for bad in ("", "7", "abc", "-5", "100000"):
            self.assertEqual(self.size({"per_page": bad}), DEFAULT_PAGE_SIZE)

from datetime import timedelta

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Company, Membership
from apps.errors import trends
from apps.ingestion.models import ErrorGroup, ErrorOccurrence
from apps.notifications.models import Notification
from apps.products.models import APIKey, Product, ProductAccess, ProductVersion

User = get_user_model()


def make(username, company, role):
    user = User.objects.create_user(username, f"{username}@t.local", "pass1234")
    Membership.objects.create(user=user, company=company, role=role)
    return user


class SparklineTest(TestCase):
    def test_an_empty_series_is_flat_and_not_rising(self):
        s = trends.sparkline([0] * 14)
        self.assertEqual((s["total"], s["peak"], s["rising"]), (0, 0, False))

    def test_the_line_has_one_point_per_day_inside_the_box(self):
        s = trends.sparkline([0, 1, 2, 3, 4])
        points = [tuple(map(float, p.split(","))) for p in s["line"].split()]
        self.assertEqual(len(points), 5)
        self.assertTrue(all(0 <= x <= s["width"] and 0 <= y <= s["height"] for x, y in points))
        self.assertEqual(points[-1][1], min(y for _, y in points))  # the peak is the highest point

    def test_a_climb_in_the_last_three_days_is_rising(self):
        self.assertTrue(trends.sparkline([0] * 8 + [1, 1, 1, 4, 5, 6])["rising"])

    def test_one_stray_hit_is_not_rising(self):
        self.assertFalse(trends.sparkline([0] * 13 + [1])["rising"])

    def test_a_steady_rate_is_not_rising(self):
        self.assertFalse(trends.sparkline([3] * 14)["rising"])


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Acme", slug="acme")
        self.owner = make("owner", self.company, "owner")
        self.admin = make("admin", self.company, "admin")
        self.dev = make("dev", self.company, "developer")
        self.product = Product.objects.create(name="App", slug="app", company=self.company)
        ProductAccess.objects.create(company=self.company, product=self.product, user=self.dev)
        self.v1 = ProductVersion.objects.create(company=self.company, product=self.product, version_string="1.0", is_current=False)
        self.v2 = ProductVersion.objects.create(company=self.company, product=self.product, version_string="2.0", is_current=True)

    def group(self, fingerprint="f", **kw):
        return ErrorGroup.objects.create(company=self.company, product=self.product, fingerprint=fingerprint, title=f"Error {fingerprint}", **kw)

    def hit(self, group, days_ago=0, version=None):
        occ = ErrorOccurrence.objects.create(company=self.company, error_group=group, version=version)
        ErrorOccurrence.objects.filter(pk=occ.pk).update(created_at=timezone.now() - timedelta(days=days_ago, hours=1))
        return occ


class AttachTrendsTest(Base):
    def test_daily_counts_land_on_the_right_days(self):
        g = self.group()
        for days in (0, 0, 1, 5):
            self.hit(g, days)
        t = trends.attach_trends([g])[0].trend
        self.assertEqual(t["counts"][-1], 2)
        self.assertEqual(t["counts"][-2], 1)
        self.assertEqual(t["counts"][-6], 1)
        self.assertEqual(t["total"], 4)

    def test_hits_older_than_the_window_are_ignored(self):
        g = self.group()
        self.hit(g, 40)
        self.assertEqual(trends.attach_trends([g])[0].trend["total"], 0)

    def test_it_is_one_query_for_many_groups(self):
        groups = [self.group(str(i), first_version=self.v1) for i in range(10)]
        for g in groups:
            self.hit(g)
        with self.assertNumQueries(3):  # counts, current versions, version labels
            trends.attach_trends(groups)
        # Ten times the groups, the same number of queries.
        more = [self.group(f"m{i}", first_version=self.v1) for i in range(30)]
        with self.assertNumQueries(3):
            trends.attach_trends(groups + more)

    def test_regression_shows_only_while_it_is_unresolved(self):
        g = self.group(regression_count=1, status="open")
        self.assertTrue(trends.attach_trends([g])[0].is_regression)
        g.status = "resolved"
        self.assertFalse(trends.attach_trends([g])[0].is_regression)

    def test_a_clean_group_is_not_a_regression(self):
        self.assertFalse(trends.attach_trends([self.group()])[0].is_regression)

    def test_new_in_release_means_first_seen_in_the_current_one(self):
        new, old, none = self.group("n", first_version=self.v2), self.group("o", first_version=self.v1), self.group("x")
        out = {g.fingerprint: g for g in trends.attach_trends([new, old, none])}
        self.assertTrue(out["n"].new_in_release)
        self.assertEqual(out["n"].first_version_label, "2.0")
        self.assertFalse(out["o"].new_in_release)
        self.assertFalse(out["x"].new_in_release)

    def test_detail_trend_splits_by_release(self):
        g = self.group()
        self.hit(g, 0, self.v2); self.hit(g, 1, self.v2); self.hit(g, 2, self.v1); self.hit(g, 2)
        d = trends.detail_trend(g)
        self.assertEqual(d["total"], 4)
        self.assertEqual(d["by_version"][0], {"version": "2.0", "count": 2})
        self.assertIn({"version": "Unknown", "count": 1}, d["by_version"])
        self.assertEqual(len(d["bars"]), 30)


class RegressionIngestTest(Base):
    def setUp(self):
        super().setUp()
        _, raw = APIKey.create_key(product=self.product, name="k")
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")

    def capture(self, version="2.0"):
        return self.api.post("/api/v1/errors/capture/", {"message": "Boom", "error_type": "E", "stacktrace": "s", "version": version}, format="json")

    def test_the_first_release_is_recorded_and_never_changes(self):
        self.capture("1.0")
        self.capture("2.0")
        self.assertEqual(ErrorGroup.objects.get().first_version, self.v1)

    def test_a_returning_resolved_error_is_flagged_and_admins_are_told_once(self):
        self.capture()
        ErrorGroup.objects.update(status="resolved")
        self.capture()
        group = ErrorGroup.objects.get()
        self.assertEqual((group.status, group.regression_count), ("open", 1))
        self.assertIsNotNone(group.regressed_at)
        told = {n.user.username for n in Notification.objects.filter(kind="regression")}
        self.assertEqual(told, {"owner", "admin"})  # not the developer
        self.capture()  # it is open now: another hit is not another regression
        self.assertEqual(ErrorGroup.objects.get().regression_count, 1)
        self.assertEqual(Notification.objects.filter(kind="regression").count(), 2)

    def test_an_ignored_error_is_not_a_regression(self):
        self.capture()
        ErrorGroup.objects.update(status="ignored")
        self.capture()
        self.assertEqual(ErrorGroup.objects.get().regression_count, 0)
        self.assertFalse(Notification.objects.filter(kind="regression").exists())

    def test_the_notice_points_at_the_error(self):
        self.capture()
        ErrorGroup.objects.update(status="resolved")
        self.capture()
        n = Notification.objects.filter(kind="regression").first()
        self.assertEqual(n.url, f"/errors/{ErrorGroup.objects.get().pk}/")


class BackfillTest(Base):
    def test_existing_groups_get_the_release_of_their_first_occurrence(self):
        from importlib import import_module

        g = self.group()
        self.hit(g, 5, None)
        self.hit(g, 4, self.v1)
        self.hit(g, 1, self.v2)
        migration = import_module("apps.ingestion.migrations.0003_error_trends")
        migration.backfill_first_version(django_apps, None)
        g.refresh_from_db()
        self.assertEqual(g.first_version, self.v1)  # the earliest occurrence that had a release


class PagesTest(Base):
    def setUp(self):
        super().setUp()
        self.g = self.group(first_version=self.v2, regression_count=1, regressed_at=timezone.now())
        for d in (0, 0, 1):
            self.hit(self.g, d, self.v2)

    def test_the_global_list_shows_the_chart_and_flags(self):
        self.client.login(username="owner", password="pass1234")
        page = self.client.get(reverse("errors:error_list")).content.decode()
        self.assertIn('class="spark', page)
        self.assertIn("Regression", page)
        self.assertIn("New in 2.0", page)

    def test_the_product_list_shows_them_too(self):
        self.client.login(username="dev", password="pass1234")
        page = self.client.get(reverse("products:product_errors", args=[self.product.pk])).content.decode()
        self.assertIn('class="spark', page)
        self.assertIn("Regression", page)

    def test_both_detail_pages_show_the_trend_and_releases(self):
        self.client.login(username="owner", password="pass1234")
        for url in (reverse("errors:error_detail", args=[self.g.pk]),
                    reverse("products:product_error_detail", args=[self.product.pk, self.g.pk])):
            page = self.client.get(url).content.decode()
            self.assertIn("Last 30 days", page, url)
            self.assertIn("Came back after being resolved 1 time", page, url)
            self.assertIn("First seen in release", page, url)

    def test_access_scoping_is_unchanged(self):
        other = Product.objects.create(name="Hidden", slug="hidden", company=self.company)
        hidden = ErrorGroup.objects.create(company=self.company, product=other, fingerprint="h", title="Hidden error")
        self.client.login(username="dev", password="pass1234")
        self.assertNotContains(self.client.get(reverse("errors:error_list")), "Hidden error")
        self.assertEqual(self.client.get(reverse("errors:error_detail", args=[hidden.pk])).status_code, 404)

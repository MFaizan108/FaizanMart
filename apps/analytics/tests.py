from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.vendors.models import Store

from .models import ProductView
from .services import (
    get_also_viewed,
    get_best_sellers,
    get_frequently_bought_together,
    get_personalized_recommendations,
    get_related_products,
)

User = get_user_model()


class AnalyticsTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Gear")
        self.vendor = User.objects.create_user(
            email="analyticsvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Analytics Store", status=Store.Status.APPROVED)
        self.product_a = Product.objects.create(
            store=self.store, category=category, name="Widget A", sku="WA-1", price="10.00",
            status=Product.Status.PUBLISHED,
        )
        self.product_b = Product.objects.create(
            store=self.store, category=category, name="Widget B", sku="WB-1", price="20.00",
            status=Product.Status.PUBLISHED,
        )
        self.customer = User.objects.create_user(
            email="analyticscustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def make_order(self, products_qty, status=Order.Status.DELIVERED):
        order = Order.objects.create(
            customer=self.customer, store=self.store, status=status, payment_method="cod",
            shipping_full_name="X", shipping_phone="0300", shipping_address_line="x", shipping_city="x",
            shipping_country="Pakistan",
        )
        for product, qty in products_qty:
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, sku=product.sku,
                unit_price=product.price, quantity=qty,
            )
        return order


class RecommendationServiceTests(AnalyticsTestBase):
    def test_related_products_same_category_excludes_self(self):
        related = list(get_related_products(self.product_a))
        self.assertIn(self.product_b, related)
        self.assertNotIn(self.product_a, related)

    def test_frequently_bought_together(self):
        self.make_order([(self.product_a, 1), (self.product_b, 1)])
        result = get_frequently_bought_together(self.product_a)
        self.assertIn(self.product_b, result)

    def test_best_sellers_ranked_by_units_sold(self):
        self.make_order([(self.product_a, 5)])
        self.make_order([(self.product_b, 1)])
        result = get_best_sellers()
        self.assertEqual(result[0], self.product_a)


class RecommendationAPITests(AnalyticsTestBase):
    def test_track_view_and_recently_viewed(self):
        self.login("analyticscustomer@example.com")
        response = self.client.post(reverse("analytics_api:track-view"), {"product": self.product_a.id})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(ProductView.objects.filter(user=self.customer).count(), 1)

        response = self.client.get(reverse("analytics_api:recently-viewed"))
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.product_a.id)

    def test_anonymous_track_view_does_not_require_auth(self):
        response = self.client.post(reverse("analytics_api:track-view"), {"product": self.product_a.id})
        self.assertEqual(response.status_code, 204)
        self.assertTrue(ProductView.objects.filter(product=self.product_a, user=None).exists())

    def test_trending_and_best_sellers_public(self):
        response = self.client.get(reverse("analytics_api:trending"))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("analytics_api:best-sellers"))
        self.assertEqual(response.status_code, 200)


class DashboardAndReportTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(email="analyticsadmin@example.com", password="AdminPass1!")
        self.make_order([(self.product_a, 2)])

    def test_vendor_dashboard_shows_revenue(self):
        self.login("analyticsvendor@example.com")
        response = self.client.get(reverse("analytics_api:vendor-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sales_count"], 1)

    def test_customer_cannot_access_vendor_dashboard(self):
        self.login("analyticscustomer@example.com")
        response = self.client.get(reverse("analytics_api:vendor-dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard(self):
        self.login("analyticsadmin@example.com", "AdminPass1!")
        response = self.client.get(reverse("analytics_api:admin-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("platform_revenue", response.data)

    def test_sales_report_scoped_to_own_store_for_vendor(self):
        self.login("analyticsvendor@example.com")
        response = self.client.get(reverse("analytics_api:report-sales"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_orders"], 1)

    def test_inventory_report_requires_staff_role(self):
        self.login("analyticscustomer@example.com")
        response = self.client.get(reverse("analytics_api:report-inventory"))
        self.assertEqual(response.status_code, 403)

        self.client.credentials()
        self.login("analyticsadmin@example.com", "AdminPass1!")
        response = self.client.get(reverse("analytics_api:report-inventory"))
        self.assertEqual(response.status_code, 200)


class AlsoViewedTests(AnalyticsTestBase):
    def test_also_viewed_from_shared_viewers(self):
        viewer = User.objects.create_user(
            email="analyticsviewer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        ProductView.objects.create(product=self.product_a, user=viewer)
        ProductView.objects.create(product=self.product_b, user=viewer)

        result = get_also_viewed(self.product_a)
        self.assertIn(self.product_b, result)
        self.assertNotIn(self.product_a, result)

    def test_endpoint_is_public(self):
        response = self.client.get(reverse("analytics_api:also-viewed", args=[self.product_a.id]))
        self.assertEqual(response.status_code, 200)


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "analytics-cache-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class TrendingCacheTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.make_order([(self.product_a, 3)])

    def test_best_sellers_response_is_served_from_cache(self):
        url = reverse("analytics_api:best-sellers")

        first = self.client.get(url)
        names = {p["name"] for p in first.data}
        self.assertIn("Widget A", names)

        # A new order that would change the ranking is invisible until the TTL expires —
        # proving the second response came from cache, not a fresh aggregate query.
        self.make_order([(self.product_b, 10)])
        second = self.client.get(url)
        self.assertEqual(second.data, first.data)


class PersonalizedRecommendationTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.other_category = Category.objects.create(name="Other")
        self.product_c = Product.objects.create(
            store=self.store, category=self.other_category, name="Widget C", sku="WC-1", price="30.00",
            status=Product.Status.PUBLISHED,
        )
        self.other_user = User.objects.create_user(
            email="analyticsotheruser@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def test_cold_start_user_falls_back_to_best_sellers(self):
        fresh_user = User.objects.create_user(
            email="analyticsfresh@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.make_order([(self.product_a, 5)])  # someone else's purchase makes product_a a best-seller

        result = get_personalized_recommendations(fresh_user)
        self.assertIn(self.product_a, result)

    def test_collaborative_signal_surfaces_cross_category_product(self):
        # customer and other_user both viewed product_a; other_user also viewed product_c,
        # which is in a *different* category, so this can only come from the collaborative
        # (shared-viewer) signal, not the content-based (same-category) one.
        ProductView.objects.create(product=self.product_a, user=self.customer)
        ProductView.objects.create(product=self.product_a, user=self.other_user)
        ProductView.objects.create(product=self.product_c, user=self.other_user)

        result = get_personalized_recommendations(self.customer)
        self.assertIn(self.product_c, result)
        self.assertNotIn(self.product_a, result)  # already interacted with, not re-recommended

    def test_content_based_signal_from_same_category(self):
        ProductView.objects.create(product=self.product_a, user=self.customer)
        result = get_personalized_recommendations(self.customer)
        self.assertIn(self.product_b, result)  # same category as product_a, no other viewers involved

    def test_for_you_endpoint_requires_auth(self):
        response = self.client.get(reverse("analytics_api:for-you"))
        self.assertEqual(response.status_code, 401)

        self.login("analyticscustomer@example.com")
        response = self.client.get(reverse("analytics_api:for-you"))
        self.assertEqual(response.status_code, 200)

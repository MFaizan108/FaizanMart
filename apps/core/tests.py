from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.vendors.models import Store

from .models import AuditLog

User = get_user_model()

# The project runs its test suite against a dummy cache (see FaizanMart/settings/test.py) so
# DRF's rate limiting doesn't leak counters between the hundreds of other test methods that
# share one test run. These throttling tests specifically need a real, working cache, scoped
# to just this class so they don't reintroduce that cross-test contamination.
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rate-limit-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class RateLimitingTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_login_is_throttled_after_five_attempts_per_minute(self):
        User.objects.create_user(email="throttle@example.com", password="S0meStrongPass!")
        url = reverse("accounts_api:login")

        for _ in range(5):
            response = self.client.post(url, {"email": "throttle@example.com", "password": "wrong"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url, {"email": "throttle@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 429)

    def test_register_is_throttled_after_five_attempts_per_minute(self):
        url = reverse("accounts_api:register")

        for i in range(5):
            response = self.client.post(url, {"email": f"reg{i}@example.com", "password": "S0meStrongPass!"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url, {"email": "regextra@example.com", "password": "S0meStrongPass!"})
        self.assertEqual(response.status_code, 429)

    def test_different_scopes_are_independent(self):
        # Exhausting the login scope shouldn't affect the separately-scoped register endpoint.
        User.objects.create_user(email="separate@example.com", password="S0meStrongPass!")
        login_url = reverse("accounts_api:login")
        for _ in range(6):
            self.client.post(login_url, {"email": "separate@example.com", "password": "wrong"})

        response = self.client.post(
            reverse("accounts_api:register"), {"email": "freshuser@example.com", "password": "S0meStrongPass!"}
        )
        self.assertNotEqual(response.status_code, 429)


class AuditLogTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Gadgets")
        self.admin = User.objects.create_superuser(email="auditadmin@example.com", password="AdminPass1!")
        self.vendor = User.objects.create_user(
            email="auditvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Audit Store", status=Store.Status.APPROVED)
        self.other_user = User.objects.create_user(
            email="auditother@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_creating_product_via_api_logs_create_action_with_attribution(self):
        self.login("auditvendor@example.com")
        response = self.client.post(
            reverse("catalog_api:product-list"),
            {"category": self.category.id, "name": "Lamp", "sku": "SKU-AUDIT-1", "price": "15.00"},
        )
        self.assertEqual(response.status_code, 201)

        log = AuditLog.objects.get(model_name="Product", object_id=str(response.data["id"]), action="create")
        self.assertEqual(log.user, self.vendor)
        self.assertIsNotNone(log.ip_address)
        self.assertEqual(log.new_value["name"], "Lamp")

    def test_updating_product_price_logs_focused_diff(self):
        product = Product.objects.create(
            store=self.store, category=self.category, name="Lamp", sku="SKU-AUDIT-2",
            price="1000.00", status=Product.Status.PUBLISHED,
        )
        self.login("auditvendor@example.com")
        response = self.client.patch(
            reverse("catalog_api:product-detail", args=[product.id]), {"price": "1200.00"}
        )
        self.assertEqual(response.status_code, 200)

        log = AuditLog.objects.get(model_name="Product", object_id=str(product.id), action="update")
        self.assertEqual(log.user, self.vendor)
        self.assertEqual(log.old_value["price"], "1000.00")
        self.assertEqual(log.new_value["price"], "1200.00")
        # Only the field that actually changed should appear in the diff.
        self.assertNotIn("name", log.new_value)

    def test_deleting_product_logs_delete_action(self):
        product = Product.objects.create(
            store=self.store, category=self.category, name="Lamp", sku="SKU-AUDIT-3",
            price="10.00", status=Product.Status.PUBLISHED,
        )
        self.login("auditvendor@example.com")
        response = self.client.delete(reverse("catalog_api:product-detail", args=[product.id]))
        self.assertEqual(response.status_code, 204)

        log = AuditLog.objects.get(model_name="Product", object_id=str(product.id), action="delete")
        self.assertEqual(log.old_value["name"], "Lamp")

    def test_audit_log_endpoint_requires_super_admin(self):
        self.login("auditother@example.com")
        response = self.client.get(reverse("core_api:audit-log-list"))
        self.assertEqual(response.status_code, 403)

        self.login("auditadmin@example.com", "AdminPass1!")
        response = self.client.get(reverse("core_api:audit-log-list"))
        self.assertEqual(response.status_code, 200)

    def test_audit_log_endpoint_filters_by_model_and_object_id(self):
        product = Product.objects.create(
            store=self.store, category=self.category, name="Lamp", sku="SKU-AUDIT-4",
            price="10.00", status=Product.Status.PUBLISHED,
        )
        self.login("auditadmin@example.com", "AdminPass1!")
        response = self.client.get(
            reverse("core_api:audit-log-list"), {"model_name": "Product", "object_id": str(product.id)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(row["model_name"] == "Product" for row in response.data["results"]))

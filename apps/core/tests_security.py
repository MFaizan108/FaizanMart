"""Formal security regression suite (Phase 11).

Complements the permission checks already embedded in each app's own tests.py —
those verify one feature's authorization rules as part of testing that feature;
this file exists purely to sweep the security surface *systematically*, in one
place, so a new endpoint that forgets a permission class or a throttle scope
gets caught here even if nobody thought to write a feature-specific test for it.

Three concerns, three classes:
  - AnonymousAccessTests   — every write/account-scoped endpoint rejects a fully
                              anonymous caller (401, not a silent 200/500).
  - RoleBypassTests        — authenticated-but-wrong-role and cross-tenant
                              requests are denied (403/404), including privilege
                              escalation via mass-assignment and a tampered JWT.
  - RateLimitEdgeCaseTests — the scoped throttles that don't already have a
                              dedicated test (otp, password_reset, checkout,
                              payment) actually trip at their configured limit.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.coupons.models import Coupon
from apps.support.models import Ticket
from apps.vendors.models import Store

User = get_user_model()


class AnonymousAccessTests(APITestCase):
    """No credentials attached: every one of these must come back 401, never a
    403 (which would mean the view considered the request *authenticated but
    unauthorized*, i.e. it treated an anonymous user as it would a logged-in
    one with the wrong role — a much more dangerous class of bug), and never
    a 2xx or 500."""

    PROTECTED_ENDPOINTS = [
        ("get", "accounts_api:me", {}),
        ("get", "accounts_api:sessions", {}),
        ("get", "accounts_api:address-list", {}),
        ("post", "cart_api:merge", {}),
        ("get", "orders_api:order-list", {}),
        ("post", "orders_api:checkout", {}),
        ("get", "payments_api:wallet", {}),
        ("get", "payments_api:payment-method-list", {}),
        ("get", "vendors_api:my-store", {}),
        ("get", "vendors_api:admin-applications", {}),
        ("post", "catalog_api:product-list", {}),
        ("post", "coupons_api:coupon-list", {}),
        ("post", "coupons_api:validate", {}),
        ("get", "support_api:ticket-list", {}),
        ("post", "support_api:faq-list", {}),
        ("patch", "sitesettings_api:settings", {}),
        ("get", "sitesettings_api:email-template-list", {}),
        ("get", "core_api:audit-log-list", {}),
    ]

    def test_protected_endpoints_reject_anonymous_requests(self):
        for method, url_name, data in self.PROTECTED_ENDPOINTS:
            with self.subTest(method=method, url=url_name):
                response = getattr(self.client, method)(reverse(url_name), data)
                self.assertEqual(
                    response.status_code,
                    401,
                    f"{method.upper()} {url_name} returned {response.status_code}, expected 401",
                )

    def test_coupon_list_read_is_public_but_write_is_not(self):
        # Contrast case for the table above: GET is intentionally AllowAny (public catalog
        # of active coupons), so it must NOT be swept into the blanket 401 check.
        response = self.client.get(reverse("coupons_api:coupon-list"))
        self.assertEqual(response.status_code, 200)


class RoleBypassTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="sec_customer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.other_customer = User.objects.create_user(
            email="sec_customer2@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.vendor_a = User.objects.create_user(
            email="sec_vendor_a@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.vendor_b = User.objects.create_user(
            email="sec_vendor_b@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.admin = User.objects.create_superuser(email="sec_admin@example.com", password="AdminPass1!")
        self.store_a = Store.objects.create(owner=self.vendor_a, name="Store A", status=Store.Status.APPROVED)
        self.store_b = Store.objects.create(owner=self.vendor_b, name="Store B", status=Store.Status.APPROVED)
        self.category = Category.objects.create(name="Gadgets")
        self.ticket = Ticket.objects.create(
            customer=self.customer, subject="Help", description="Where is my order?"
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        access_token = response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return access_token

    # --- cross-role escalation ---------------------------------------------------

    def test_customer_cannot_access_vendor_store_endpoint(self):
        self.login("sec_customer@example.com")
        response = self.client.get(reverse("vendors_api:my-store"))
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_list_or_approve_vendor_applications(self):
        self.login("sec_customer@example.com")
        response = self.client.get(reverse("vendors_api:admin-applications"))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse("vendors_api:admin-approve", args=[self.store_a.id]))
        self.assertEqual(response.status_code, 403)
        self.store_a.refresh_from_db()
        self.assertEqual(self.store_a.status, Store.Status.APPROVED)  # unchanged (was already approved)

    def test_customer_cannot_create_platform_wide_coupon(self):
        self.login("sec_customer@example.com")
        response = self.client.post(
            reverse("coupons_api:coupon-list"),
            {
                "code": "HACKED10",
                "discount_type": Coupon.DiscountType.PERCENTAGE,
                "value": "10",
                "valid_from": timezone.now().isoformat(),
                "valid_until": (timezone.now() + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Coupon.objects.filter(code="HACKED10").exists())

    def test_vendor_cannot_create_coupon_for_a_store_they_do_not_own(self):
        self.login("sec_vendor_a@example.com")
        response = self.client.post(
            reverse("coupons_api:coupon-list"),
            {
                "code": "STEALSTORE",
                "discount_type": Coupon.DiscountType.FIXED,
                "value": "5",
                "store": self.store_b.id,
                "valid_from": timezone.now().isoformat(),
                "valid_until": (timezone.now() + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Coupon.objects.filter(code="STEALSTORE").exists())

    def test_customer_cannot_patch_site_settings(self):
        self.login("sec_customer@example.com")
        response = self.client.patch(reverse("sitesettings_api:settings"), {"site_name": "Hacked"})
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_manage_email_templates(self):
        self.login("sec_customer@example.com")
        response = self.client.get(reverse("sitesettings_api:email-template-list"))
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_product_without_a_store(self):
        self.login("sec_customer@example.com")
        response = self.client.post(
            reverse("catalog_api:product-list"),
            {"category": self.category.id, "name": "Sneaky", "sku": "SKU-SEC-1", "price": "9.99"},
        )
        self.assertIn(response.status_code, (400, 403))
        self.assertFalse(Product.objects.filter(sku="SKU-SEC-1").exists())

    # --- cross-tenant isolation ----------------------------------------------------

    def test_customer_cannot_view_another_customers_support_ticket(self):
        self.login("sec_customer2@example.com")
        response = self.client.get(reverse("support_api:ticket-detail", args=[self.ticket.id]))
        # Scoped out of the queryset entirely rather than a 403, so its existence isn't leaked.
        self.assertEqual(response.status_code, 404)

    def test_vendor_a_cannot_update_vendor_bs_store_via_their_own_endpoint(self):
        # MyStoreView.get_object() always resolves to request.user's own store, so this
        # confirms there's no way to pass store_b's id in and have it accepted instead.
        self.login("sec_vendor_a@example.com")
        response = self.client.patch(reverse("vendors_api:my-store"), {"name": "Renamed", "id": self.store_b.id})
        self.assertEqual(response.status_code, 200)
        self.store_b.refresh_from_db()
        self.assertEqual(self.store_b.name, "Store B")  # untouched

    # --- privilege escalation / tampering -------------------------------------------

    def test_role_field_cannot_be_escalated_via_profile_update(self):
        self.login("sec_customer@example.com")
        response = self.client.patch(reverse("accounts_api:me"), {"role": User.Role.SUPER_ADMIN})
        self.assertEqual(response.status_code, 200)  # request "succeeds"...
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)  # ...but role is read-only, so it's a no-op

    def test_tampered_jwt_is_rejected(self):
        real_token = self.login("sec_customer@example.com")
        tampered = real_token[:-4] + "abcd"
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered}")
        response = self.client.get(reverse("accounts_api:me"))
        self.assertEqual(response.status_code, 401)

    def test_malformed_authorization_header_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = self.client.get(reverse("accounts_api:me"))
        self.assertEqual(response.status_code, 401)


# Same rationale as core/tests.py's RateLimitingTests: the shared test-suite cache is a
# DummyCache (see FaizanMart/settings/test.py) so throttle counters don't leak across the
# other ~200 tests in the run; these need a real per-class cache to actually count hits.
LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "security-rate-limit-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class RateLimitEdgeCaseTests(APITestCase):
    """Covers the scoped throttles core/tests.py's RateLimitingTests doesn't already
    exercise (that file only covers auth_login/auth_register)."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="sec_ratelimit@example.com", password="S0meStrongPass!")
        response = self.client.post(
            reverse("accounts_api:login"), {"email": "sec_ratelimit@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_password_reset_request_is_throttled_after_five_per_minute(self):
        url = reverse("accounts_api:password-reset")
        for _ in range(5):
            response = self.client.post(url, {"email": "sec_ratelimit@example.com"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url, {"email": "sec_ratelimit@example.com"})
        self.assertEqual(response.status_code, 429)

    def test_otp_enable_is_throttled_after_five_per_minute(self):
        url = reverse("accounts_api:2fa-enable")
        for _ in range(5):
            response = self.client.post(url)
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 429)

    def test_checkout_is_throttled_after_ten_per_minute(self):
        url = reverse("orders_api:checkout")
        for _ in range(10):
            response = self.client.post(url, {})
            self.assertNotEqual(response.status_code, 429)  # 400s from the empty payload are fine

        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 429)

    def test_wallet_add_money_is_throttled_after_ten_per_minute(self):
        url = reverse("payments_api:wallet-add-money")
        for _ in range(10):
            response = self.client.post(url, {"amount": "1.00", "reason": "top-up"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url, {"amount": "1.00", "reason": "top-up"})
        self.assertEqual(response.status_code, 429)

    def test_scoped_throttle_does_not_leak_into_the_global_user_rate(self):
        # Exhausting a 5/min scope shouldn't affect an endpoint under the general 300/min
        # default throttle — confirms ScopedRateThrottle counters are keyed independently.
        reset_url = reverse("accounts_api:password-reset")
        for _ in range(6):
            self.client.post(reset_url, {"email": "sec_ratelimit@example.com"})

        response = self.client.get(reverse("accounts_api:me"))
        self.assertNotEqual(response.status_code, 429)

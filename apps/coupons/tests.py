from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.vendors.models import Store

from . import services
from .models import Coupon

User = get_user_model()


def make_coupon(**kwargs):
    now = timezone.now()
    defaults = {
        "code": "SAVE10",
        "discount_type": Coupon.DiscountType.PERCENTAGE,
        "value": Decimal("10"),
        "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=1),
    }
    defaults.update(kwargs)
    return Coupon.objects.create(**defaults)


class CouponServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="couponuser@example.com", password="S0meStrongPass!")

    def test_percentage_discount(self):
        coupon = make_coupon(discount_type=Coupon.DiscountType.PERCENTAGE, value=Decimal("10"))
        discount = services.compute_discount(coupon, Decimal("200"))
        self.assertEqual(discount, Decimal("20.00"))

    def test_fixed_discount_capped_at_subtotal(self):
        coupon = make_coupon(discount_type=Coupon.DiscountType.FIXED, value=Decimal("50"))
        discount = services.compute_discount(coupon, Decimal("30"))
        self.assertEqual(discount, Decimal("30"))

    def test_expired_coupon_rejected(self):
        now = timezone.now()
        coupon = make_coupon(valid_from=now - timedelta(days=10), valid_until=now - timedelta(days=1))
        with self.assertRaises(ValueError):
            services.validate_coupon(coupon.code, self.user, Decimal("100"))

    def test_usage_limit_enforced(self):
        coupon = make_coupon(usage_limit=1, used_count=1)
        with self.assertRaises(ValueError):
            services.validate_coupon(coupon.code, self.user, Decimal("100"))

    def test_min_order_amount_enforced(self):
        coupon = make_coupon(min_order_amount=Decimal("100"))
        with self.assertRaises(ValueError):
            services.validate_coupon(coupon.code, self.user, Decimal("50"))


class CouponAPITests(APITestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(
            email="couponvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Coupon Store", status=Store.Status.APPROVED)
        self.customer = User.objects.create_user(
            email="couponcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_vendor_can_create_coupon_for_own_store_only(self):
        self.login("couponvendor@example.com")
        now = timezone.now()
        response = self.client.post(
            reverse("coupons_api:coupon-list"),
            {
                "code": "VENDOR5",
                "discount_type": "fixed",
                "value": "5.00",
                "store": self.store.id,
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_vendor_cannot_create_platform_wide_coupon(self):
        self.login("couponvendor@example.com")
        now = timezone.now()
        response = self.client.post(
            reverse("coupons_api:coupon-list"),
            {
                "code": "PLATFORM5",
                "discount_type": "fixed",
                "value": "5.00",
                "valid_from": now.isoformat(),
                "valid_until": (now + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_validate_endpoint(self):
        make_coupon(code="APITEST", discount_type=Coupon.DiscountType.PERCENTAGE, value=Decimal("15"))
        self.login("couponcustomer@example.com")
        response = self.client.post(
            reverse("coupons_api:validate"), {"code": "APITEST", "subtotal": "100.00"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["estimated_discount"], Decimal("15.00"))

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.payments.models import Wallet
from apps.vendors.models import Store

from . import services
from .models import Banner, FlashSale, NewsletterSubscriber, ReferralSignup

User = get_user_model()


class MarketingTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Deals")
        vendor = User.objects.create_user(
            email="marketingvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        store = Store.objects.create(owner=vendor, name="Marketing Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=store, category=category, name="Deal Item", sku="DEAL-1", price="40.00",
            status=Product.Status.PUBLISHED,
        )
        self.admin = User.objects.create_superuser(email="marketingadmin@example.com", password="AdminPass1!")
        self.customer_a = User.objects.create_user(
            email="referrera@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.customer_b = User.objects.create_user(
            email="referredb@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class BannerTests(MarketingTestBase):
    def test_public_sees_only_active_banners(self):
        Banner.objects.create(title="Live", image="x.jpg", is_active=True)
        Banner.objects.create(title="Off", image="x.jpg", is_active=False)
        response = self.client.get(reverse("marketing_api:banner-list"))
        self.assertEqual(response.data["count"], 1)

    def test_non_admin_cannot_create_banner(self):
        self.login("referrera@example.com")
        response = self.client.post(reverse("marketing_api:banner-list"), {"title": "X", "image": ""})
        self.assertEqual(response.status_code, 403)


class FlashSaleTests(MarketingTestBase):
    def test_sale_price_computed_correctly(self):
        # self.product.price was assigned as a plain string in setUp() and only becomes a real
        # Decimal once it round-trips through the DB (or DRF validation, in the real API path).
        self.product.refresh_from_db()
        now = timezone.now()
        sale = FlashSale.objects.create(
            name="Big Sale", starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1)
        )
        item = sale.items.create(product=self.product, discount_percentage=Decimal("25"))
        self.assertEqual(item.sale_price, Decimal("30.00"))
        self.assertTrue(sale.is_live)


class NewsletterTests(MarketingTestBase):
    def test_subscribe_and_unsubscribe(self):
        response = self.client.post(
            reverse("marketing_api:newsletter-subscribe"), {"email": "fan@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(NewsletterSubscriber.objects.get(email="fan@example.com").is_active)

        self.client.post(reverse("marketing_api:newsletter-unsubscribe"), {"email": "fan@example.com"})
        self.assertFalse(NewsletterSubscriber.objects.get(email="fan@example.com").is_active)


class ReferralTests(MarketingTestBase):
    def test_apply_referral_grants_wallet_bonus_to_both(self):
        self.login("referrera@example.com")
        code_response = self.client.get(reverse("marketing_api:referral-my-code"))
        code = code_response.data["code"]

        self.client.credentials()
        self.login("referredb@example.com")
        response = self.client.post(reverse("marketing_api:referral-apply"), {"code": code})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(Wallet.objects.get(user=self.customer_a).balance, services.REFERRER_BONUS)
        self.assertEqual(Wallet.objects.get(user=self.customer_b).balance, services.REFERRED_USER_BONUS)
        self.assertTrue(ReferralSignup.objects.filter(referrer=self.customer_a, referred_user=self.customer_b).exists())

    def test_cannot_apply_referral_twice(self):
        self.login("referrera@example.com")
        code_response = self.client.get(reverse("marketing_api:referral-my-code"))
        code = code_response.data["code"]
        self.client.credentials()

        self.login("referredb@example.com")
        self.client.post(reverse("marketing_api:referral-apply"), {"code": code})
        response = self.client.post(reverse("marketing_api:referral-apply"), {"code": code})
        self.assertEqual(response.status_code, 400)

    def test_cannot_refer_self(self):
        self.login("referrera@example.com")
        code_response = self.client.get(reverse("marketing_api:referral-my-code"))
        code = code_response.data["code"]

        response = self.client.post(reverse("marketing_api:referral-apply"), {"code": code})
        self.assertEqual(response.status_code, 400)

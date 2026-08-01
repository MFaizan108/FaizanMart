from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.coupons.models import Coupon
from apps.inventory.models import Stock, Warehouse
from apps.notifications.models import Notification
from apps.vendors.models import Store

from .models import Order

User = get_user_model()

VALID_SHIPPING = {
    "shipping_full_name": "Jane Doe",
    "shipping_phone": "0300-1234567",
    "shipping_address_line": "123 Main St",
    "shipping_city": "Karachi",
    "shipping_country": "Pakistan",
    "payment_method": "cod",
}


class OrdersTestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Gear")
        self.warehouse = Warehouse.objects.create(name="WH", code="WH-ORD")

        self.vendor_a = User.objects.create_user(
            email="ordervendora@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store_a = Store.objects.create(owner=self.vendor_a, name="Store A", status=Store.Status.APPROVED)
        self.product_a = Product.objects.create(
            store=self.store_a, category=self.category, name="Product A", sku="A-1", price="10.00",
            status=Product.Status.PUBLISHED,
        )
        Stock.objects.create(product=self.product_a, warehouse=self.warehouse, quantity=10)

        self.vendor_b = User.objects.create_user(
            email="ordervendorb@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store_b = Store.objects.create(owner=self.vendor_b, name="Store B", status=Store.Status.APPROVED)
        self.product_b = Product.objects.create(
            store=self.store_b, category=self.category, name="Product B", sku="B-1", price="25.00",
            status=Product.Status.PUBLISHED,
        )
        Stock.objects.create(product=self.product_b, warehouse=self.warehouse, quantity=3)

        self.customer = User.objects.create_user(
            email="ordercustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def add_to_cart(self, user, product, quantity):
        cart, _ = Cart.objects.get_or_create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        return cart


class CheckoutTests(OrdersTestBase):
    def test_multi_vendor_checkout_creates_one_order_per_store_and_reserves_stock(self):
        self.add_to_cart(self.customer, self.product_a, 2)
        self.add_to_cart(self.customer, self.product_b, 1)
        self.login("ordercustomer@example.com")

        response = self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data), 2)

        stores = {order["store_name"] for order in response.data}
        self.assertEqual(stores, {"Store A", "Store B"})

        stock_a = Stock.objects.get(product=self.product_a, warehouse=self.warehouse)
        self.assertEqual(stock_a.reserved_quantity, 2)
        stock_b = Stock.objects.get(product=self.product_b, warehouse=self.warehouse)
        self.assertEqual(stock_b.reserved_quantity, 1)

        # Cart is cleared after a successful checkout.
        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.items.count(), 0)

    def test_checkout_fails_cleanly_with_no_partial_reservation(self):
        self.add_to_cart(self.customer, self.product_a, 2)
        self.add_to_cart(self.customer, self.product_b, 999)  # more than the 3 in stock
        self.login("ordercustomer@example.com")

        response = self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)
        self.assertEqual(response.status_code, 400)

        self.assertEqual(Order.objects.count(), 0)
        stock_a = Stock.objects.get(product=self.product_a, warehouse=self.warehouse)
        self.assertEqual(stock_a.reserved_quantity, 0)  # rolled back, not left dangling

        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.items.count(), 2)  # not cleared on failure

    def test_checkout_rejects_missing_billing_when_not_same_as_shipping(self):
        self.add_to_cart(self.customer, self.product_a, 1)
        self.login("ordercustomer@example.com")
        payload = dict(VALID_SHIPPING, billing_same_as_shipping=False)
        response = self.client.post(reverse("orders_api:checkout"), payload)
        self.assertEqual(response.status_code, 400)

    def test_checkout_with_empty_cart_rejected(self):
        self.login("ordercustomer@example.com")
        response = self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)
        self.assertEqual(response.status_code, 400)


class TransitionTests(OrdersTestBase):
    def setUp(self):
        super().setUp()
        self.add_to_cart(self.customer, self.product_a, 2)
        self.login("ordercustomer@example.com")
        checkout_response = self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)
        self.order_id = checkout_response.data[0]["id"]
        self.client.credentials()

    def test_illegal_transition_rejected(self):
        self.login("ordervendora@example.com")
        response = self.client.post(
            reverse("orders_api:order-transition", args=[self.order_id]), {"status": "shipped"}
        )
        self.assertEqual(response.status_code, 400)

    def test_shipping_decrements_stock_and_clears_reservation(self):
        self.login("ordervendora@example.com")
        self.client.post(reverse("orders_api:order-transition", args=[self.order_id]), {"status": "processing"})
        self.client.post(reverse("orders_api:order-transition", args=[self.order_id]), {"status": "packed"})
        response = self.client.post(
            reverse("orders_api:order-transition", args=[self.order_id]), {"status": "shipped"}
        )
        self.assertEqual(response.status_code, 200)

        stock = Stock.objects.get(product=self.product_a, warehouse=self.warehouse)
        self.assertEqual(stock.quantity, 8)  # 10 - 2 actually shipped out
        self.assertEqual(stock.reserved_quantity, 0)  # reservation cleared, not double counted

    def test_cancel_before_shipment_releases_reservation_without_deducting(self):
        self.login("ordercustomer@example.com")
        response = self.client.post(
            reverse("orders_api:order-cancel", args=[self.order_id]), {"reason": "Changed my mind"}
        )
        self.assertEqual(response.status_code, 200)

        stock = Stock.objects.get(product=self.product_a, warehouse=self.warehouse)
        self.assertEqual(stock.quantity, 10)  # untouched
        self.assertEqual(stock.reserved_quantity, 0)  # released

    def test_other_customer_cannot_cancel_order(self):
        other = User.objects.create_user(
            email="othercustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.login("othercustomer@example.com")
        response = self.client.post(reverse("orders_api:order-cancel", args=[self.order_id]), {})
        self.assertEqual(response.status_code, 404)  # not even visible in their queryset

    def test_other_vendor_cannot_transition_order(self):
        self.login("ordervendorb@example.com")
        response = self.client.post(
            reverse("orders_api:order-transition", args=[self.order_id]), {"status": "processing"}
        )
        self.assertEqual(response.status_code, 404)  # store B's queryset never includes store A's order

    def test_customer_cannot_transition_own_order(self):
        self.login("ordercustomer@example.com")
        response = self.client.post(
            reverse("orders_api:order-transition", args=[self.order_id]), {"status": "processing"}
        )
        self.assertEqual(response.status_code, 403)  # visible (their own order) but not theirs to manage


class CouponAndNotificationIntegrationTests(OrdersTestBase):
    def test_coupon_code_applies_discount_at_checkout(self):
        now = timezone.now()
        Coupon.objects.create(
            code="SAVE5",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("5.00"),
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
        )
        self.add_to_cart(self.customer, self.product_a, 2)  # subtotal 20.00
        self.login("ordercustomer@example.com")

        response = self.client.post(
            reverse("orders_api:checkout"), dict(VALID_SHIPPING, coupon_code="save5")
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data[0]["discount_amount"], "5.00")
        self.assertEqual(response.data[0]["total_amount"], "15.00")  # 20 - 5

    def test_store_specific_coupon_rejected_for_other_store(self):
        now = timezone.now()
        Coupon.objects.create(
            code="STOREB",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("5.00"),
            store=self.store_b,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
        )
        self.add_to_cart(self.customer, self.product_a, 1)  # only store A in cart
        self.login("ordercustomer@example.com")

        response = self.client.post(
            reverse("orders_api:checkout"), dict(VALID_SHIPPING, coupon_code="STOREB")
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_notifies_customer_and_vendor(self):
        self.add_to_cart(self.customer, self.product_a, 1)
        self.login("ordercustomer@example.com")
        self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)

        self.assertTrue(Notification.objects.filter(user=self.customer, notification_type="order_update").exists())
        self.assertTrue(Notification.objects.filter(user=self.vendor_a, notification_type="order_update").exists())

    def test_transition_notifies_customer(self):
        self.add_to_cart(self.customer, self.product_a, 1)
        self.login("ordercustomer@example.com")
        checkout_response = self.client.post(reverse("orders_api:checkout"), VALID_SHIPPING)
        order_id = checkout_response.data[0]["id"]
        Notification.objects.all().delete()

        self.client.credentials()
        self.login("ordervendora@example.com")
        self.client.post(reverse("orders_api:order-transition", args=[order_id]), {"status": "processing"})

        self.assertTrue(
            Notification.objects.filter(user=self.customer, notification_type="order_update").exists()
        )

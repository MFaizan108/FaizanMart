from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.orders.models import Order
from apps.vendors.models import Store

from .models import Courier, Shipment

User = get_user_model()


class ShippingTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Ship Stuff")
        self.vendor = User.objects.create_user(
            email="shipvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Ship Store", status=Store.Status.APPROVED)
        product = Product.objects.create(
            store=self.store, category=category, name="Box", sku="BOX-1", price="5.00",
            status=Product.Status.PUBLISHED,
        )
        self.customer = User.objects.create_user(
            email="shipcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.order = Order.objects.create(
            customer=self.customer, store=self.store, status=Order.Status.PACKED, payment_method="cod",
            shipping_full_name="C", shipping_phone="0300", shipping_address_line="x", shipping_city="x",
            shipping_country="Pakistan",
        )
        self.courier = Courier.objects.create(name="TCS", tracking_url_template="https://t/{tracking_number}")

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class ShipmentTests(ShippingTestBase):
    def test_vendor_can_create_shipment_for_own_order(self):
        self.login("shipvendor@example.com")
        response = self.client.post(
            reverse("shipping_api:shipment-list"),
            {"order": self.order.id, "courier": self.courier.id, "tracking_number": "TRK123"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Shipment.Status.LABEL_CREATED)

    def test_customer_cannot_create_shipment(self):
        self.login("shipcustomer@example.com")
        response = self.client.post(
            reverse("shipping_api:shipment-list"),
            {"order": self.order.id, "courier": self.courier.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_status_progression_and_illegal_jump_rejected(self):
        self.login("shipvendor@example.com")
        create_response = self.client.post(
            reverse("shipping_api:shipment-list"), {"order": self.order.id, "courier": self.courier.id}
        )
        shipment_id = create_response.data["id"]

        bad = self.client.post(
            reverse("shipping_api:shipment-update-status", args=[shipment_id]), {"status": "delivered"}
        )
        self.assertEqual(bad.status_code, 400)

        good = self.client.post(
            reverse("shipping_api:shipment-update-status", args=[shipment_id]), {"status": "in_transit"}
        )
        self.assertEqual(good.status_code, 200)
        self.assertIsNotNone(good.data["shipped_at"])

    def test_customer_can_view_own_order_shipment(self):
        self.login("shipvendor@example.com")
        create_response = self.client.post(
            reverse("shipping_api:shipment-list"), {"order": self.order.id, "courier": self.courier.id}
        )
        self.client.credentials()

        self.login("shipcustomer@example.com")
        response = self.client.get(reverse("shipping_api:shipment-detail", args=[create_response.data["id"]]))
        self.assertEqual(response.status_code, 200)

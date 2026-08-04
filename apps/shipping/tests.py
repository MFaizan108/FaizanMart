from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Order
from apps.vendors.models import Store

from . import services
from .models import Courier, DeliveryAssignment, Shipment, ShippingRule
from .rules import calculate_shipping_cost

User = get_user_model()


class ShippingTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Ship Stuff")
        self.vendor = User.objects.create_user(
            email="shipvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Ship Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
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


class ShippingRuleCalculationTests(APITestCase):
    def test_city_rule_matches(self):
        ShippingRule.objects.create(name="Lahore", city="Lahore", shipping_cost="150.00")
        self.assertEqual(calculate_shipping_cost(country="Pakistan", city="Lahore"), Decimal("150.00"))

    def test_no_matching_rule_returns_none(self):
        self.assertIsNone(calculate_shipping_cost(country="Pakistan", city="Nowhere"))

    def test_inactive_rule_is_ignored(self):
        ShippingRule.objects.create(name="Lahore", city="Lahore", shipping_cost="150.00", is_active=False)
        self.assertIsNone(calculate_shipping_cost(country="Pakistan", city="Lahore"))

    def test_free_shipping_over_threshold_beats_flat_city_rate_via_priority(self):
        ShippingRule.objects.create(name="Karachi flat", city="Karachi", shipping_cost="250.00", priority=0)
        ShippingRule.objects.create(
            name="Free over 5000", min_order_amount="5000.01", is_free_shipping=True, priority=10
        )
        self.assertEqual(
            calculate_shipping_cost(country="Pakistan", city="Karachi", order_amount=Decimal("6000")), Decimal("0")
        )
        self.assertEqual(
            calculate_shipping_cost(country="Pakistan", city="Karachi", order_amount=Decimal("100")),
            Decimal("250.00"),
        )

    def test_weight_range_rule(self):
        ShippingRule.objects.create(name="Heavy", min_weight="5.00", shipping_cost="500.00")
        self.assertIsNone(calculate_shipping_cost(total_weight=Decimal("2")))
        self.assertEqual(calculate_shipping_cost(total_weight=Decimal("6")), Decimal("500.00"))

    def test_store_specific_rule_only_matches_that_store(self):
        vendor = User.objects.create_user(
            email="ruleowner@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        store = Store.objects.create(owner=vendor, name="Rule Store", status=Store.Status.APPROVED)
        other_vendor = User.objects.create_user(
            email="otherowner@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        other_store = Store.objects.create(owner=other_vendor, name="Other Store", status=Store.Status.APPROVED)
        ShippingRule.objects.create(name="Store rate", store=store, shipping_cost="99.00")

        self.assertEqual(calculate_shipping_cost(store=store), Decimal("99.00"))
        self.assertIsNone(calculate_shipping_cost(store=other_store))
        self.assertIsNone(calculate_shipping_cost(store=None))


class CheckoutShippingCostTests(ShippingTestBase):
    def setUp(self):
        super().setUp()
        self.warehouse = Warehouse.objects.create(name="Ship WH", code="WH-SHIPCHK")
        Stock.objects.create(product=self.product, warehouse=self.warehouse, quantity=10)

    def _checkout(self, extra=None):
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.login("shipcustomer@example.com")
        payload = {
            "shipping_full_name": "Jane", "shipping_phone": "0300", "shipping_address_line": "x",
            "shipping_city": "Lahore", "shipping_country": "Pakistan", "payment_method": "cod",
        }
        if extra:
            payload.update(extra)
        return self.client.post(reverse("orders_api:checkout"), payload)

    def test_checkout_uses_matching_shipping_rule(self):
        ShippingRule.objects.create(name="Lahore", city="Lahore", shipping_cost="150.00")
        response = self._checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data[0]["shipping_cost"], "150.00")

    def test_checkout_ignores_client_supplied_shipping_cost(self):
        ShippingRule.objects.create(name="Lahore", city="Lahore", shipping_cost="150.00")
        # Even if a client tries to smuggle a shipping_cost in, the server-computed rule wins.
        response = self._checkout({"shipping_cost": "1.00"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data[0]["shipping_cost"], "150.00")

    def test_checkout_falls_back_to_zero_with_no_matching_rule(self):
        response = self._checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data[0]["shipping_cost"], "0.00")


class DeliveryAssignmentTests(ShippingTestBase):
    def setUp(self):
        super().setUp()
        self.warehouse = Warehouse.objects.create(name="Deliv WH", code="WH-DELIV")
        Stock.objects.create(product=self.product, warehouse=self.warehouse, quantity=10, reserved_quantity=1)
        self.admin = User.objects.create_superuser(email="shipadmin@example.com", password="AdminPass1!")
        self.delivery_boy = User.objects.create_user(
            email="deliveryboy@example.com", password="S0meStrongPass!", role=User.Role.DELIVERY_BOY
        )
        self.other_delivery_boy = User.objects.create_user(
            email="otherdeliveryboy@example.com", password="S0meStrongPass!", role=User.Role.DELIVERY_BOY
        )

    def test_only_staff_can_assign_delivery(self):
        self.login("shipvendor@example.com")
        response = self.client.post(
            reverse("shipping_api:delivery-list"),
            {"order": self.order.id, "delivery_boy": self.delivery_boy.id},
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_assign_non_delivery_boy(self):
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "shipadmin@example.com", "password": "AdminPass1!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        response = self.client.post(
            reverse("shipping_api:delivery-list"),
            {"order": self.order.id, "delivery_boy": self.customer.id},
        )
        self.assertEqual(response.status_code, 400)

    def test_assign_and_full_delivery_flow_transitions_order(self):
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "shipadmin@example.com", "password": "AdminPass1!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        create = self.client.post(
            reverse("shipping_api:delivery-list"),
            {"order": self.order.id, "delivery_boy": self.delivery_boy.id},
        )
        self.assertEqual(create.status_code, 201)
        assignment_id = create.data["id"]
        self.client.credentials()

        db_login = self.client.post(
            reverse("accounts_api:login"), {"email": "deliveryboy@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {db_login.data['access']}")

        picked_up = self.client.post(
            reverse("shipping_api:delivery-update-status", args=[assignment_id]), {"status": "picked_up"}
        )
        self.assertEqual(picked_up.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)

        out = self.client.post(
            reverse("shipping_api:delivery-update-status", args=[assignment_id]), {"status": "out_for_delivery"}
        )
        self.assertEqual(out.status_code, 200)

        delivered = self.client.post(
            reverse("shipping_api:delivery-update-status", args=[assignment_id]), {"status": "delivered"}
        )
        self.assertEqual(delivered.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERED)

    def test_other_delivery_boy_cannot_update_someone_elses_assignment(self):
        assignment = services.assign_delivery(self.order, self.delivery_boy)
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "otherdeliveryboy@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.post(
            reverse("shipping_api:delivery-update-status", args=[assignment.id]), {"status": "picked_up"}
        )
        # get_queryset() already scopes delivery boys to their own assignments, so this
        # 404s (not found in their queryset) rather than 403 — same pattern as cross-user
        # access elsewhere in the codebase (e.g. accounts Address tests).
        self.assertEqual(response.status_code, 404)

    def test_failed_delivery_allows_reassignment(self):
        assignment = services.assign_delivery(self.order, self.delivery_boy)
        services.update_delivery_status(assignment, DeliveryAssignment.Status.FAILED, failure_reason="Not home")
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.Status.FAILED)

        # Order never left PACKED since pickup never happened; a fresh assignment can be made.
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PACKED)
        new_assignment = services.assign_delivery(self.order, self.other_delivery_boy)
        self.assertNotEqual(new_assignment.id, assignment.id)

    def test_cannot_double_assign_while_one_is_active(self):
        services.assign_delivery(self.order, self.delivery_boy)
        with self.assertRaises(ValueError):
            services.assign_delivery(self.order, self.other_delivery_boy)

    def test_my_deliveries_dashboard_scoped_to_own_assignments(self):
        services.assign_delivery(self.order, self.delivery_boy)
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "deliveryboy@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = self.client.get(reverse("shipping_api:my-deliveries"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

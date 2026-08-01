from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.vendors.models import Store

from .models import InventoryLog, Stock, StockTransfer, Warehouse

User = get_user_model()


class InventoryTestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Widgets")
        self.vendor = User.objects.create_user(
            email="stockvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Stock Vendor Shop", status=Store.Status.APPROVED)
        self.other_vendor = User.objects.create_user(
            email="othervendor2@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.other_store = Store.objects.create(
            owner=self.other_vendor, name="Other Shop", status=Store.Status.APPROVED
        )
        self.product = Product.objects.create(
            store=self.store, category=self.category, name="Widget", sku="WID-1", price="9.99"
        )
        self.manager = User.objects.create_user(
            email="whmanager@example.com", password="S0meStrongPass!", role=User.Role.WAREHOUSE_MANAGER
        )
        self.warehouse_a = Warehouse.objects.create(name="Warehouse A", code="WH-A")
        self.warehouse_b = Warehouse.objects.create(name="Warehouse B", code="WH-B")

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class StockAccessTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.stock = Stock.objects.create(product=self.product, warehouse=self.warehouse_a, quantity=50)

    def test_vendor_can_read_own_product_stock(self):
        self.login("stockvendor@example.com")
        response = self.client.get(reverse("inventory_api:stock-list"))
        self.assertEqual(response.data["count"], 1)

    def test_other_vendor_cannot_see_stock(self):
        self.login("othervendor2@example.com")
        response = self.client.get(reverse("inventory_api:stock-list"))
        self.assertEqual(response.data["count"], 0)

    def test_vendor_cannot_restock(self):
        self.login("stockvendor@example.com")
        response = self.client.post(
            reverse("inventory_api:stock-restock", args=[self.stock.id]), {"quantity": 10}
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_restock_and_log_is_written(self):
        self.login("whmanager@example.com")
        response = self.client.post(
            reverse("inventory_api:stock-restock", args=[self.stock.id]), {"quantity": 20, "note": "PO #1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 70)
        log = InventoryLog.objects.latest("created_at")
        self.assertEqual(log.change_type, InventoryLog.ChangeType.RESTOCK)
        self.assertEqual(log.quantity_delta, 20)
        self.assertEqual(log.resulting_quantity, 70)


class ReserveReleaseTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.stock = Stock.objects.create(product=self.product, warehouse=self.warehouse_a, quantity=10)

    def test_reserve_more_than_available_is_rejected(self):
        self.login("whmanager@example.com")
        response = self.client.post(
            reverse("inventory_api:stock-reserve", args=[self.stock.id]), {"quantity": 999}
        )
        self.assertEqual(response.status_code, 400)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 0)

    def test_reserve_then_release(self):
        self.login("whmanager@example.com")
        response = self.client.post(
            reverse("inventory_api:stock-reserve", args=[self.stock.id]), {"quantity": 4}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["available_quantity"], 6)

        response = self.client.post(
            reverse("inventory_api:stock-release", args=[self.stock.id]), {"quantity": 4}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["available_quantity"], 10)


class TransferTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.stock_a = Stock.objects.create(product=self.product, warehouse=self.warehouse_a, quantity=15)

    def test_transfer_with_insufficient_stock_rejected(self):
        self.login("whmanager@example.com")
        response = self.client.post(
            reverse("inventory_api:transfer-list"),
            {
                "product": self.product.id,
                "from_warehouse": self.warehouse_a.id,
                "to_warehouse": self.warehouse_b.id,
                "quantity": 999,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_transfer_completion_moves_quantity(self):
        self.login("whmanager@example.com")
        create_response = self.client.post(
            reverse("inventory_api:transfer-list"),
            {
                "product": self.product.id,
                "from_warehouse": self.warehouse_a.id,
                "to_warehouse": self.warehouse_b.id,
                "quantity": 5,
            },
        )
        self.assertEqual(create_response.status_code, 201)
        transfer_id = create_response.data["id"]

        complete_response = self.client.post(
            reverse("inventory_api:transfer-complete", args=[transfer_id])
        )
        self.assertEqual(complete_response.status_code, 200)
        self.assertEqual(complete_response.data["status"], StockTransfer.Status.COMPLETED)

        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.quantity, 10)
        stock_b = Stock.objects.get(product=self.product, warehouse=self.warehouse_b)
        self.assertEqual(stock_b.quantity, 5)


class AlertTests(InventoryTestBase):
    def setUp(self):
        super().setUp()
        self.low = Stock.objects.create(
            product=self.product, warehouse=self.warehouse_a, quantity=3, low_stock_threshold=10
        )
        product_2 = Product.objects.create(
            store=self.store, category=self.category, name="Widget Two", sku="WID-2", price="5.00"
        )
        self.out = Stock.objects.create(product=product_2, warehouse=self.warehouse_a, quantity=0)

    def test_low_stock_alert(self):
        self.login("whmanager@example.com")
        response = self.client.get(reverse("inventory_api:alert-low-stock"))
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(self.low.id, ids)
        self.assertNotIn(self.out.id, ids)

    def test_out_of_stock_alert(self):
        self.login("whmanager@example.com")
        response = self.client.get(reverse("inventory_api:alert-out-of-stock"))
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(self.out.id, ids)
        self.assertNotIn(self.low.id, ids)

    def test_vendor_cannot_access_alerts(self):
        self.login("stockvendor@example.com")
        response = self.client.get(reverse("inventory_api:alert-low-stock"))
        self.assertEqual(response.status_code, 403)

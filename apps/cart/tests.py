from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.inventory.models import Stock, Warehouse
from apps.vendors.models import Store

from .models import Cart, CartItem

User = get_user_model()


class CartTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Books")
        vendor = User.objects.create_user(
            email="cartvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        store = Store.objects.create(owner=vendor, name="Cart Vendor Shop", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=store,
            category=category,
            name="Novel",
            sku="BOOK-1",
            price="12.50",
            status=Product.Status.PUBLISHED,
        )
        self.limited_product = Product.objects.create(
            store=store,
            category=category,
            name="Limited Gadget",
            sku="GADGET-1",
            price="30.00",
            status=Product.Status.PUBLISHED,
        )
        warehouse = Warehouse.objects.create(name="WH", code="WH-1")
        Stock.objects.create(product=self.limited_product, warehouse=warehouse, quantity=2)

        self.customer = User.objects.create_user(
            email="cartcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class GuestCartTests(CartTestBase):
    def test_guest_cart_created_and_token_persists(self):
        response = self.client.get(reverse("cart_api:detail"))
        self.assertEqual(response.status_code, 200)
        token = response.data["guest_token"]
        self.assertIsNotNone(token)

        add_response = self.client.post(
            reverse("cart_api:item-list"),
            {"product": self.product.id, "quantity": 2},
            HTTP_X_CART_TOKEN=str(token),
        )
        self.assertEqual(add_response.status_code, 201)
        self.assertEqual(add_response.data["items_count"], 2)

        # Same token round-trips to the same cart.
        follow_up = self.client.get(reverse("cart_api:detail"), HTTP_X_CART_TOKEN=str(token))
        self.assertEqual(follow_up.data["items_count"], 2)

        # No token -> a brand new (empty) guest cart.
        no_token = self.client.get(reverse("cart_api:detail"))
        self.assertEqual(no_token.data["items_count"], 0)

    def test_adding_beyond_available_stock_rejected(self):
        response = self.client.get(reverse("cart_api:detail"))
        token = response.data["guest_token"]
        add_response = self.client.post(
            reverse("cart_api:item-list"),
            {"product": self.limited_product.id, "quantity": 5},
            HTTP_X_CART_TOKEN=str(token),
        )
        self.assertEqual(add_response.status_code, 400)


class AuthenticatedCartTests(CartTestBase):
    def test_cart_persists_without_token(self):
        self.login("cartcustomer@example.com")
        self.client.post(reverse("cart_api:item-list"), {"product": self.product.id, "quantity": 1})

        response = self.client.get(reverse("cart_api:detail"))
        self.assertEqual(response.data["items_count"], 1)
        self.assertEqual(Cart.objects.filter(user=self.customer).count(), 1)

    def test_cannot_touch_another_users_cart_item(self):
        self.login("cartcustomer@example.com")
        add_response = self.client.post(
            reverse("cart_api:item-list"), {"product": self.product.id, "quantity": 1}
        )
        item_id = add_response.data["items"][0]["id"]

        other = User.objects.create_user(
            email="other_customer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.client.credentials()
        self.login("other_customer@example.com")
        response = self.client.delete(reverse("cart_api:item-detail", args=[item_id]))
        self.assertEqual(response.status_code, 404)


class CartMergeTests(CartTestBase):
    def test_merge_sums_overlapping_items(self):
        guest_response = self.client.get(reverse("cart_api:detail"))
        guest_token = guest_response.data["guest_token"]
        self.client.post(
            reverse("cart_api:item-list"),
            {"product": self.product.id, "quantity": 2},
            HTTP_X_CART_TOKEN=str(guest_token),
        )

        self.login("cartcustomer@example.com")
        self.client.post(reverse("cart_api:item-list"), {"product": self.product.id, "quantity": 1})

        merge_response = self.client.post(reverse("cart_api:merge"), {"guest_token": str(guest_token)})
        self.assertEqual(merge_response.status_code, 200)
        self.assertEqual(merge_response.data["items_count"], 3)
        self.assertFalse(Cart.objects.filter(guest_token=guest_token).exists())

    def test_merge_requires_authentication(self):
        response = self.client.post(reverse("cart_api:merge"), {"guest_token": "not-a-real-token"})
        self.assertEqual(response.status_code, 401)

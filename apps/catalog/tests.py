import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from apps.vendors.models import Store

from .models import Category, Product

User = get_user_model()


def make_test_image():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("test.png", buffer.read(), content_type="image/png")


def make_vendor(email, store_status=Store.Status.APPROVED):
    user = User.objects.create_user(email=email, password="S0meStrongPass!", role=User.Role.VENDOR)
    store = Store.objects.create(owner=user, name=f"{email} shop", status=store_status)
    return user, store


class CatalogTestBase(APITestCase):
    def login(self, email, password="S0meStrongPass!"):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class CategoryBrandPermissionTests(CatalogTestBase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="catadmin@example.com", password="AdminPass1!")
        self.vendor, self.store = make_vendor("catvendor@example.com")

    def test_anonymous_can_read_but_not_write(self):
        response = self.client.get(reverse("catalog_api:category-list"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse("catalog_api:category-list"), {"name": "Electronics"})
        self.assertEqual(response.status_code, 401)

    def test_vendor_cannot_create_category(self):
        self.login("catvendor@example.com")
        response = self.client.post(reverse("catalog_api:category-list"), {"name": "Electronics"})
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_category(self):
        self.login("catadmin@example.com", "AdminPass1!")
        response = self.client.post(reverse("catalog_api:category-list"), {"name": "Electronics"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["slug"], "electronics")


class ProductVisibilityTests(CatalogTestBase):
    def setUp(self):
        self.category = Category.objects.create(name="Gadgets")
        self.vendor, self.store = make_vendor("visvendor@example.com")
        self.other_vendor, self.other_store = make_vendor("othervendor@example.com")

        self.published = Product.objects.create(
            store=self.store,
            category=self.category,
            name="Published Widget",
            sku="SKU-PUB-1",
            price="10.00",
            status=Product.Status.PUBLISHED,
        )
        self.draft = Product.objects.create(
            store=self.store,
            category=self.category,
            name="Draft Widget",
            sku="SKU-DRAFT-1",
            price="10.00",
            status=Product.Status.DRAFT,
        )

    def test_anonymous_sees_only_published(self):
        response = self.client.get(reverse("catalog_api:product-list"))
        names = [p["name"] for p in response.data["results"]]
        self.assertIn("Published Widget", names)
        self.assertNotIn("Draft Widget", names)

    def test_owner_sees_own_draft_too(self):
        self.login("visvendor@example.com")
        response = self.client.get(reverse("catalog_api:product-list"))
        names = [p["name"] for p in response.data["results"]]
        self.assertIn("Published Widget", names)
        self.assertIn("Draft Widget", names)

    def test_other_vendor_does_not_see_this_draft(self):
        self.login("othervendor@example.com")
        response = self.client.get(reverse("catalog_api:product-list"))
        names = [p["name"] for p in response.data["results"]]
        self.assertIn("Published Widget", names)
        self.assertNotIn("Draft Widget", names)


class ProductCreateUpdateTests(CatalogTestBase):
    def setUp(self):
        self.category = Category.objects.create(name="Home")
        self.approved_vendor, self.approved_store = make_vendor("approved@example.com")
        self.pending_vendor, self.pending_store = make_vendor(
            "pending@example.com", store_status=Store.Status.PENDING
        )
        self.customer = User.objects.create_user(
            email="cust@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def test_pending_vendor_cannot_create_product(self):
        self.login("pending@example.com")
        response = self.client.post(
            reverse("catalog_api:product-list"),
            {"category": self.category.id, "name": "Lamp", "sku": "SKU-1", "price": "5.00"},
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_create_product(self):
        self.login("cust@example.com")
        response = self.client.post(
            reverse("catalog_api:product-list"),
            {"category": self.category.id, "name": "Lamp", "sku": "SKU-2", "price": "5.00"},
        )
        self.assertEqual(response.status_code, 403)

    def test_approved_vendor_can_create_and_it_is_nested_on_read(self):
        self.login("approved@example.com")
        response = self.client.post(
            reverse("catalog_api:product-list"),
            {"category": self.category.id, "name": "Lamp", "sku": "SKU-3", "price": "15.00"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["category"]["name"], "Home")
        self.assertEqual(response.data["store"], self.approved_store.id)
        product_id = response.data["id"]

        image_response = self.client.post(
            reverse("catalog_api:product-image-list"),
            {"product": product_id, "alt_text": "front view", "image": make_test_image()},
            format="multipart",
        )
        self.assertEqual(image_response.status_code, 201)

        detail = self.client.get(reverse("catalog_api:product-detail", args=[product_id]))
        self.assertEqual(len(detail.data["images"]), 1)

    def test_vendor_cannot_edit_another_vendors_product(self):
        # Published so it's visible in the other vendor's queryset — proves the
        # object-permission layer itself rejects it (403), not just queryset scoping (404).
        product = Product.objects.create(
            store=self.approved_store,
            category=self.category,
            name="Owned By Approved",
            sku="SKU-4",
            price="20.00",
            status=Product.Status.PUBLISHED,
        )
        self.login("pending@example.com")
        response = self.client.patch(
            reverse("catalog_api:product-detail", args=[product.id]), {"name": "Hijacked"}
        )
        self.assertEqual(response.status_code, 403)

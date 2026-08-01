from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Store

User = get_user_model()


class VendorRegistrationTests(APITestCase):
    def test_register_creates_user_and_pending_store(self):
        response = self.client.post(
            reverse("vendors_api:register"),
            {
                "email": "vendor1@example.com",
                "password": "S0meStrongPass!",
                "store_name": "Vendor One Shop",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Store.Status.PENDING)
        self.assertEqual(response.data["slug"], "vendor-one-shop")

        user = User.objects.get(email="vendor1@example.com")
        self.assertEqual(user.role, User.Role.VENDOR)
        self.assertTrue(Store.objects.filter(owner=user, status=Store.Status.PENDING).exists())

    def test_duplicate_slug_gets_suffix(self):
        self.client.post(
            reverse("vendors_api:register"),
            {"email": "a@example.com", "password": "S0meStrongPass!", "store_name": "Same Name"},
        )
        response = self.client.post(
            reverse("vendors_api:register"),
            {"email": "b@example.com", "password": "S0meStrongPass!", "store_name": "Same Name"},
        )
        self.assertEqual(response.data["slug"], "same-name-1")


class MyStoreAccessTests(APITestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(
            email="vendor2@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Vendor Two Shop")
        self.customer = User.objects.create_user(
            email="customer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def _login(self, email, password):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_non_vendor_forbidden(self):
        self._login("customer@example.com", "S0meStrongPass!")
        response = self.client.get(reverse("vendors_api:my-store"))
        self.assertEqual(response.status_code, 403)

    def test_vendor_can_view_and_update_own_store(self):
        self._login("vendor2@example.com", "S0meStrongPass!")
        response = self.client.get(reverse("vendors_api:my-store"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Vendor Two Shop")

        response = self.client.patch(reverse("vendors_api:my-store"), {"description": "We sell things."})
        self.assertEqual(response.status_code, 200)
        self.store.refresh_from_db()
        self.assertEqual(self.store.description, "We sell things.")

    def test_vendor_cannot_set_status_directly(self):
        self._login("vendor2@example.com", "S0meStrongPass!")
        self.client.patch(reverse("vendors_api:my-store"), {"status": Store.Status.APPROVED})
        self.store.refresh_from_db()
        self.assertEqual(self.store.status, Store.Status.PENDING)


class VendorApprovalTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin2@example.com", password="AdminPass1!")
        self.vendor = User.objects.create_user(
            email="vendor3@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Vendor Three Shop")

    def _login(self, email, password):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_non_admin_forbidden(self):
        self._login("vendor3@example.com", "S0meStrongPass!")
        response = self.client.get(reverse("vendors_api:admin-applications"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_approve_and_reject(self):
        self._login("admin2@example.com", "AdminPass1!")

        response = self.client.get(reverse("vendors_api:admin-applications"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        response = self.client.post(reverse("vendors_api:admin-approve", args=[self.store.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Store.Status.APPROVED)

        response = self.client.post(
            reverse("vendors_api:admin-reject", args=[self.store.pk]), {"reason": "Docs incomplete"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Store.Status.REJECTED)
        self.assertEqual(response.data["rejection_reason"], "Docs incomplete")

    def test_resubmit_after_rejection(self):
        self._login("admin2@example.com", "AdminPass1!")
        self.client.post(
            reverse("vendors_api:admin-reject", args=[self.store.pk]), {"reason": "Missing bank info"}
        )
        self.client.credentials()

        self._login("vendor3@example.com", "S0meStrongPass!")
        response = self.client.post(reverse("vendors_api:store-resubmit"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Store.Status.PENDING)

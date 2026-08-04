from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import SiteSettings

User = get_user_model()


class SiteSettingsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="settingsadmin@example.com", password="AdminPass1!")
        self.customer = User.objects.create_user(
            email="settingscustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email, password):
        response = self.client.post(reverse("accounts_api:login"), {"email": email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_public_can_read_settings(self):
        response = self.client.get(reverse("sitesettings_api:settings"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["currency_code"], "PKR")

    def test_non_admin_cannot_update_settings(self):
        self.login("settingscustomer@example.com", "S0meStrongPass!")
        response = self.client.patch(reverse("sitesettings_api:settings"), {"site_name": "Hacked"})
        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_settings_and_it_stays_singleton(self):
        self.login("settingsadmin@example.com", "AdminPass1!")
        response = self.client.patch(reverse("sitesettings_api:settings"), {"site_name": "FaizanMart PK"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["site_name"], "FaizanMart PK")
        self.assertEqual(SiteSettings.objects.count(), 1)


class EmailTemplateTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="templateadmin@example.com", password="AdminPass1!")

    def login(self):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": "templateadmin@example.com", "password": "AdminPass1!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_admin_can_manage_email_templates(self):
        self.login()
        response = self.client.post(
            reverse("sitesettings_api:email-template-list"),
            {"key": "order_placed", "subject": "Your order", "body": "Thanks {{ name }}"},
        )
        self.assertEqual(response.status_code, 201)

    def test_anonymous_cannot_list_email_templates(self):
        response = self.client.get(reverse("sitesettings_api:email-template-list"))
        self.assertEqual(response.status_code, 401)

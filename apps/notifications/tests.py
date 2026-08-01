from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from . import services
from .models import Notification

User = get_user_model()


class NotificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="notifyme@example.com", password="S0meStrongPass!")
        self.other = User.objects.create_user(email="notother@example.com", password="S0meStrongPass!")

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_user_only_sees_own_notifications(self):
        services.notify(self.user, "Hello", "World")
        services.notify(self.other, "Not yours", "")

        self.login("notifyme@example.com")
        response = self.client.get(reverse("notifications_api:notification-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Hello")

    def test_mark_read_and_mark_all_read(self):
        n1 = services.notify(self.user, "One")
        services.notify(self.user, "Two")
        self.login("notifyme@example.com")

        response = self.client.post(reverse("notifications_api:notification-mark-read", args=[n1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

        self.client.post(reverse("notifications_api:notification-mark-all-read"))
        self.assertEqual(Notification.objects.filter(user=self.user, is_read=False).count(), 0)

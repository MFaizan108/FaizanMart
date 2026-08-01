from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from . import services
from .models import Wallet

User = get_user_model()


class WalletServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="walletuser@example.com", password="S0meStrongPass!")

    def test_credit_and_debit(self):
        services.credit_wallet(self.user, 100, reason="top-up")
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, 100)

        services.debit_wallet(self.user, 40, reason="purchase")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 60)

    def test_debit_more_than_balance_rejected(self):
        services.credit_wallet(self.user, 10)
        with self.assertRaises(ValueError):
            services.debit_wallet(self.user, 50)


class WalletAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="walletapi@example.com", password="S0meStrongPass!")

    def login(self):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": "walletapi@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_add_money_and_view_transactions(self):
        self.login()
        response = self.client.post(reverse("payments_api:wallet-add-money"), {"amount": "50.00"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], "50.00")

        response = self.client.get(reverse("payments_api:wallet-transactions"))
        self.assertEqual(response.data["count"], 1)

    def test_wallet_requires_auth(self):
        response = self.client.get(reverse("payments_api:wallet"))
        self.assertEqual(response.status_code, 401)

from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework.test import APITestCase

from . import services
from .models import LoginHistory, TwoFactorAuth, UserSession

User = get_user_model()


class RegistrationAndLoginTests(APITestCase):
    def test_register_verify_and_login_flow(self):
        register_url = reverse("accounts_api:register")
        response = self.client.post(
            register_url,
            {"email": "alice@example.com", "password": "S0meStrongPass!", "first_name": "Alice"},
        )
        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)

        # Login before verifying email still works (verification isn't a login gate here).
        login_url = reverse("accounts_api:login")
        response = self.client.post(login_url, {"email": "alice@example.com", "password": "S0meStrongPass!"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

        # Wrong password fails and is recorded.
        response = self.client.post(login_url, {"email": "alice@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            LoginHistory.objects.filter(email_attempted="alice@example.com", was_successful=False).exists()
        )

        # Extract uid/token from the "sent" email body via services directly (deterministic, no HTML parsing).
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from .tokens import email_verification_token

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        verify_url = reverse("accounts_api:verify-email", args=[uidb64, token])
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_me_endpoint_requires_auth(self):
        response = self.client.get(reverse("accounts_api:me"))
        self.assertEqual(response.status_code, 401)


class TwoFactorTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="bob@example.com", password="S0meStrongPass!")

    def _login(self):
        return self.client.post(
            reverse("accounts_api:login"), {"email": "bob@example.com", "password": "S0meStrongPass!"}
        )

    def _authenticate(self):
        response = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_enable_confirm_and_login_requires_2fa(self):
        self._authenticate()

        response = self.client.post(reverse("accounts_api:2fa-enable"))
        self.assertEqual(response.status_code, 200)
        secret = response.data["secret"]

        code = pyotp.TOTP(secret).now()
        response = self.client.post(reverse("accounts_api:2fa-confirm"), {"code": code})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TwoFactorAuth.objects.get(user=self.user).is_enabled)

        self.client.credentials()  # clear auth
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("two_factor_required"))
        pending_token = response.data["pending_token"]

        bad = self.client.post(
            reverse("accounts_api:login-2fa-verify"), {"pending_token": pending_token, "code": "000000"}
        )
        self.assertEqual(bad.status_code, 400)

        good_code = pyotp.TOTP(secret).now()
        good = self.client.post(
            reverse("accounts_api:login-2fa-verify"), {"pending_token": pending_token, "code": good_code}
        )
        self.assertEqual(good.status_code, 200)
        self.assertIn("access", good.data)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="carol@example.com", password="OldPassword1!")

    def test_reset_flow(self):
        response = self.client.post(reverse("accounts_api:password-reset"), {"email": "carol@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse("accounts_api:password-reset-confirm"),
            {"uidb64": uidb64, "token": token, "new_password": "NewPassword1!"},
        )
        self.assertEqual(response.status_code, 200)

        login = self.client.post(
            reverse("accounts_api:login"), {"email": "carol@example.com", "password": "NewPassword1!"}
        )
        self.assertEqual(login.status_code, 200)


class LogoutAndSessionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="dave@example.com", password="S0meStrongPass!")

    def test_logout_blacklists_refresh_and_deactivates_sessions(self):
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "dave@example.com", "password": "S0meStrongPass!"}
        )
        access, refresh = login.data["access"], login.data["refresh"]
        self.assertEqual(UserSession.objects.filter(user=self.user, is_active=True).count(), 1)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(reverse("accounts_api:logout"), {"refresh": refresh})
        self.assertEqual(response.status_code, 205)
        self.assertEqual(UserSession.objects.filter(user=self.user, is_active=True).count(), 0)

        refresh_response = self.client.post(reverse("accounts_api:token-refresh"), {"refresh": refresh})
        self.assertEqual(refresh_response.status_code, 401)


class GoogleLoginTests(APITestCase):
    @patch("apps.accounts.services.google_id_token.verify_oauth2_token")
    def test_google_login_creates_user(self, mock_verify):
        mock_verify.return_value = {"email": "eve@example.com", "given_name": "Eve", "family_name": "X"}
        with self.settings(GOOGLE_OAUTH_CLIENT_ID="dummy-client-id"):
            response = self.client.post(reverse("accounts_api:google-login"), {"id_token": "fake-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        user = User.objects.get(email="eve@example.com")
        self.assertTrue(user.is_email_verified)
        self.assertEqual(user.role, User.Role.CUSTOMER)


class SessionTemplateFlowTests(APITestCase):
    def test_register_login_logout_via_templates(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "frank@example.com",
                "first_name": "Frank",
                "last_name": "",
                "phone_number": "",
                "password1": "S0meStrongPass!",
                "password2": "S0meStrongPass!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="frank@example.com").exists())

        response = self.client.post(
            reverse("accounts:login"), {"email": "frank@example.com", "password": "S0meStrongPass!"}
        )
        self.assertRedirects(response, reverse("accounts:profile"))

        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))

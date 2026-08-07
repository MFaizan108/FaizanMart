from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from . import services
from .models import Address, LoginHistory, TwoFactorAuth, UserSession
from .tasks import cleanup_expired_sessions_task

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

        # Login is gated on email verification — simulate having clicked the link before
        # exercising the rest of the logged-in flow below.
        User.objects.filter(email="frank@example.com").update(is_email_verified=True)

        response = self.client.post(
            reverse("accounts:login"), {"email": "frank@example.com", "password": "S0meStrongPass!"}
        )
        self.assertRedirects(response, reverse("storefront:home"))

        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))


class AddressBookTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="grace@example.com", password="S0meStrongPass!")
        self.other_user = User.objects.create_user(email="heidi@example.com", password="S0meStrongPass!")
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "grace@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def _address_payload(self, **overrides):
        payload = {
            "label": "Home",
            "full_name": "Grace Hopper",
            "phone_number": "03001234567",
            "address_line1": "1 Main St",
            "city": "Lahore",
            "country": "Pakistan",
        }
        payload.update(overrides)
        return payload

    def test_first_address_becomes_default_for_shipping_and_billing(self):
        response = self.client.post(reverse("accounts_api:address-list"), self._address_payload())
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_default_shipping"])
        self.assertTrue(response.data["is_default_billing"])

    def test_second_address_does_not_auto_become_default(self):
        self.client.post(reverse("accounts_api:address-list"), self._address_payload(label="Home"))
        response = self.client.post(
            reverse("accounts_api:address-list"), self._address_payload(label="Office", city="Karachi")
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["is_default_shipping"])
        self.assertFalse(response.data["is_default_billing"])

    def test_set_default_shipping_clears_previous_default(self):
        first = self.client.post(reverse("accounts_api:address-list"), self._address_payload(label="Home")).data
        second = self.client.post(
            reverse("accounts_api:address-list"), self._address_payload(label="Office", city="Karachi")
        ).data

        response = self.client.post(
            reverse("accounts_api:address-set-default-shipping", args=[second["id"]])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_default_shipping"])

        first_address = Address.objects.get(pk=first["id"])
        self.assertFalse(first_address.is_default_shipping)
        # Billing default is independent and untouched by the shipping-only action.
        self.assertTrue(first_address.is_default_billing)

    def test_deleting_default_address_promotes_another(self):
        first = self.client.post(reverse("accounts_api:address-list"), self._address_payload(label="Home")).data
        self.client.post(
            reverse("accounts_api:address-list"), self._address_payload(label="Office", city="Karachi")
        ).data

        response = self.client.delete(reverse("accounts_api:address-detail", args=[first["id"]]))
        self.assertEqual(response.status_code, 204)

        remaining = Address.objects.get(user=self.user)
        self.assertTrue(remaining.is_default_shipping)
        self.assertTrue(remaining.is_default_billing)

    def test_user_cannot_see_or_modify_another_users_address(self):
        other_address = services.create_address(
            self.other_user,
            label="Secret",
            full_name="Heidi",
            phone_number="03000000000",
            address_line1="Hidden St",
            city="Multan",
            country="Pakistan",
        )

        list_response = self.client.get(reverse("accounts_api:address-list"))
        self.assertEqual(list_response.data["count"] if "count" in list_response.data else len(list_response.data), 0)

        detail_response = self.client.get(reverse("accounts_api:address-detail", args=[other_address.id]))
        self.assertEqual(detail_response.status_code, 404)

    def test_unauthenticated_access_denied(self):
        self.client.credentials()
        response = self.client.get(reverse("accounts_api:address-list"))
        self.assertEqual(response.status_code, 401)


class SessionCleanupTaskTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cleanup@example.com", password="S0meStrongPass!")

    def test_cleanup_deactivates_old_sessions_and_trims_login_history(self):
        old_cutoff = timezone.now() - timedelta(days=45)
        recent_session = UserSession.objects.create(user=self.user, is_active=True)
        stale_session = UserSession.objects.create(user=self.user, is_active=True)
        UserSession.objects.filter(pk=stale_session.pk).update(last_seen_at=old_cutoff)

        recent_login = LoginHistory.objects.create(
            user=self.user, email_attempted=self.user.email, method="password", was_successful=True
        )
        stale_login = LoginHistory.objects.create(
            user=self.user, email_attempted=self.user.email, method="password", was_successful=True
        )
        LoginHistory.objects.filter(pk=stale_login.pk).update(created_at=old_cutoff)

        result = cleanup_expired_sessions_task(retention_days=30)

        self.assertEqual(result["sessions_deactivated"], 1)
        self.assertEqual(result["login_history_deleted"], 1)

        recent_session.refresh_from_db()
        stale_session.refresh_from_db()
        self.assertTrue(recent_session.is_active)
        self.assertFalse(stale_session.is_active)

        self.assertTrue(LoginHistory.objects.filter(pk=recent_login.pk).exists())
        self.assertFalse(LoginHistory.objects.filter(pk=stale_login.pk).exists())

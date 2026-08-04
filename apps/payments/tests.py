from unittest.mock import MagicMock, patch

import stripe as stripe_sdk
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, Product
from apps.inventory.models import Stock, Warehouse
from apps.orders.models import Order
from apps.vendors.models import Store

from . import services
from .models import PaymentTransaction, SavedPaymentMethod, StripeCustomer, Wallet
from .services import easypaisa as easypaisa_gateway
from .services import jazzcash as jazzcash_gateway

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


class SavedPaymentMethodTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="pmuser@example.com", password="S0meStrongPass!")
        self.other_user = User.objects.create_user(email="pmother@example.com", password="S0meStrongPass!")
        login = self.client.post(
            reverse("accounts_api:login"), {"email": "pmuser@example.com", "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def _save(self, user, **overrides):
        fields = {
            "provider": SavedPaymentMethod.Provider.STRIPE,
            "provider_customer_id": f"cus_{user.pk}",
            "provider_payment_method_id": overrides.pop("provider_payment_method_id", f"pm_{user.pk}_a"),
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2030,
        }
        fields.update(overrides)
        return services.save_payment_method(user, **fields)

    def test_first_saved_method_becomes_default(self):
        pm = self._save(self.user)
        self.assertTrue(pm.is_default)

    def test_second_saved_method_not_auto_default(self):
        self._save(self.user, provider_payment_method_id="pm_a")
        second = self._save(self.user, provider_payment_method_id="pm_b")
        self.assertFalse(second.is_default)

    def test_list_only_returns_own_methods_without_raw_provider_ids(self):
        self._save(self.user, provider_payment_method_id="pm_mine")
        self._save(self.other_user, provider_payment_method_id="pm_theirs")

        response = self.client.get(reverse("payments_api:payment-method-list"))
        self.assertEqual(response.data["count"], 1)
        self.assertNotIn("provider_payment_method_id", response.data["results"][0])
        self.assertNotIn("provider_customer_id", response.data["results"][0])

    def test_set_default_via_api_clears_previous_default(self):
        first = self._save(self.user, provider_payment_method_id="pm_a")
        second = self._save(self.user, provider_payment_method_id="pm_b")

        response = self.client.post(
            reverse("payments_api:payment-method-set-default", args=[second.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_default"])

        first.refresh_from_db()
        self.assertFalse(first.is_default)

    def test_deleting_default_method_promotes_another(self):
        first = self._save(self.user, provider_payment_method_id="pm_a")
        self._save(self.user, provider_payment_method_id="pm_b")

        response = self.client.delete(reverse("payments_api:payment-method-detail", args=[first.id]))
        self.assertEqual(response.status_code, 204)

        remaining = SavedPaymentMethod.objects.get(user=self.user)
        self.assertTrue(remaining.is_default)

    def test_cannot_access_another_users_payment_method(self):
        other_pm = self._save(self.other_user, provider_payment_method_id="pm_theirs")
        response = self.client.delete(reverse("payments_api:payment-method-detail", args=[other_pm.id]))
        self.assertEqual(response.status_code, 404)


@override_settings(STRIPE_SECRET_KEY="sk_test_dummy", STRIPE_WEBHOOK_SECRET="whsec_test_dummy")
class StripeIntegrationTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Gear")
        self.warehouse = Warehouse.objects.create(name="WH", code="WH-STRIPE")

        self.vendor = User.objects.create_user(
            email="stripevendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=self.store, category=self.category, name="Widget", sku="W-1", price="20.00",
            status=Product.Status.PUBLISHED,
        )
        Stock.objects.create(product=self.product, warehouse=self.warehouse, quantity=10)

        self.customer = User.objects.create_user(
            email="stripecustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.accountant = User.objects.create_user(
            email="stripeaccountant@example.com", password="S0meStrongPass!", role=User.Role.ACCOUNTANT
        )

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _checkout(self):
        Cart.objects.filter(user=self.customer).delete()
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.login("stripecustomer@example.com")
        return self.client.post(
            reverse("orders_api:checkout"),
            {
                "shipping_full_name": "Jane Doe",
                "shipping_phone": "0300-1234567",
                "shipping_address_line": "123 Main St",
                "shipping_city": "Karachi",
                "shipping_country": "Pakistan",
                "payment_method": "stripe",
            },
        )

    @patch("stripe.PaymentIntent.create")
    @patch("stripe.Customer.create")
    def test_checkout_with_stripe_creates_payment_intent_and_pending_transaction(self, mock_customer, mock_intent):
        mock_customer.return_value = MagicMock(id="cus_test123")
        mock_intent.return_value = MagicMock(id="pi_test123", client_secret="pi_test123_secret_abc")

        response = self._checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["client_secret"], "pi_test123_secret_abc")
        self.assertEqual(len(response.data["orders"]), 1)

        order = Order.objects.get(order_number=response.data["orders"][0]["order_number"])
        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.method, "stripe")
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.reference, "pi_test123")
        self.assertTrue(StripeCustomer.objects.filter(user=self.customer, stripe_customer_id="cus_test123").exists())

        mock_intent.assert_called_once()
        self.assertEqual(mock_intent.call_args.kwargs["amount"], 2000)  # $20.00 -> cents
        self.assertEqual(mock_intent.call_args.kwargs["currency"], "usd")

    def _create_pending_order_with_transaction(self, reference="pi_webhook_test"):
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        from apps.orders import services as orders_services

        orders = orders_services.place_order(
            user=self.customer,
            order_fields={
                "shipping_full_name": "Jane Doe",
                "shipping_phone": "0300-1234567",
                "shipping_address_line": "123 Main St",
                "shipping_city": "Karachi",
                "shipping_state": "",
                "shipping_postal_code": "",
                "shipping_country": "Pakistan",
                "billing_same_as_shipping": True,
                "billing_full_name": "",
                "billing_phone": "",
                "billing_address_line": "",
                "billing_city": "",
                "billing_state": "",
                "billing_postal_code": "",
                "billing_country": "",
                "payment_method": "stripe",
                "coupon_code": "",
                "shipping_cost": 0,
                "tax_amount": 0,
            },
        )
        order = orders[0]
        services.record_payment(
            order, method="stripe", amount=order.total_amount,
            status=PaymentTransaction.Status.PENDING, reference=reference,
        )
        return order

    def _post_webhook(self, event):
        with patch("stripe.Webhook.construct_event", return_value=event):
            return self.client.post(
                reverse("payments_api:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="dummy",
            )

    def test_webhook_payment_succeeded_marks_order_paid_and_processing(self):
        order = self._create_pending_order_with_transaction(reference="pi_success")
        event = {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_success"}}}

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.status, Order.Status.PROCESSING)
        txn = PaymentTransaction.objects.get(order=order, method="stripe")
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)

    def test_webhook_payment_failed_marks_order_failed_without_advancing_status(self):
        order = self._create_pending_order_with_transaction(reference="pi_failed")
        event = {"type": "payment_intent.payment_failed", "data": {"object": {"id": "pi_failed"}}}

        response = self._post_webhook(event)
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_webhook_invalid_signature_rejected(self):
        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe_sdk.error.SignatureVerificationError("bad sig", "sig_header"),
        ):
            response = self.client.post(
                reverse("payments_api:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="dummy",
            )
        self.assertEqual(response.status_code, 400)

    @patch("stripe.Refund.create")
    def test_refund_stripe_payment_is_idempotent(self, mock_refund):
        mock_refund.return_value = MagicMock(id="re_test123")

        order = self._create_pending_order_with_transaction(reference="pi_paid")
        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status"])
        PaymentTransaction.objects.filter(order=order, method="stripe").update(
            status=PaymentTransaction.Status.SUCCESS
        )

        self.login("stripeaccountant@example.com")
        response = self.client.post(reverse("payments_api:refund-stripe", args=[order.id]))
        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.REFUNDED)
        self.assertTrue(
            PaymentTransaction.objects.filter(order=order, method="stripe_refund", reference="re_test123").exists()
        )

        second = self.client.post(reverse("payments_api:refund-stripe", args=[order.id]))
        self.assertEqual(second.status_code, 400)
        mock_refund.assert_called_once()

    @patch("stripe.PaymentMethod.attach")
    @patch("stripe.PaymentMethod.retrieve")
    @patch("stripe.SetupIntent.create")
    @patch("stripe.Customer.create")
    def test_setup_intent_and_attach_new_card(self, mock_customer, mock_setup_intent, mock_retrieve, mock_attach):
        mock_customer.return_value = MagicMock(id="cus_attach_test")
        mock_setup_intent.return_value = MagicMock(client_secret="seti_test_secret")
        mock_retrieve.return_value = MagicMock(
            customer=None,
            card=MagicMock(brand="visa", last4="4242", exp_month=12, exp_year=2030),
        )

        self.login("stripecustomer@example.com")

        setup_response = self.client.post(reverse("payments_api:payment-method-setup-intent"))
        self.assertEqual(setup_response.status_code, 200)
        self.assertEqual(setup_response.data["client_secret"], "seti_test_secret")

        attach_response = self.client.post(
            reverse("payments_api:payment-method-attach"), {"payment_method_id": "pm_new_card"}
        )
        self.assertEqual(attach_response.status_code, 201)
        self.assertEqual(attach_response.data["card_brand"], "visa")
        self.assertEqual(attach_response.data["card_last4"], "4242")
        self.assertTrue(attach_response.data["is_default"])


class RedirectGatewayTestBase(APITestCase):
    """Shared fixtures for JazzCash/EasyPaisa: both are hosted-checkout redirect gateways
    verified via a locally-recomputed hash, so no external SDK mocking is needed — the tests
    exercise our own hash/verify/callback logic end to end."""

    def setUp(self):
        self.category = Category.objects.create(name="Gear")
        self.warehouse = Warehouse.objects.create(name="WH", code=f"WH-{self._testMethodName[:8]}")

        self.vendor = User.objects.create_user(
            email=f"{self._testMethodName}vendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=self.vendor, name="Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=self.store, category=self.category, name="Widget", sku=f"W-{self._testMethodName[:8]}",
            price="20.00", status=Product.Status.PUBLISHED,
        )
        Stock.objects.create(product=self.product, warehouse=self.warehouse, quantity=10)

        self.customer = User.objects.create_user(
            email=f"{self._testMethodName}customer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _checkout(self, payment_method):
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.login(self.customer.email)
        return self.client.post(
            reverse("orders_api:checkout"),
            {
                "shipping_full_name": "Jane Doe",
                "shipping_phone": "0300-1234567",
                "shipping_address_line": "123 Main St",
                "shipping_city": "Karachi",
                "shipping_country": "Pakistan",
                "payment_method": payment_method,
            },
        )

    def _place_order_directly(self, payment_method):
        from apps.orders import services as orders_services

        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        orders = orders_services.place_order(
            user=self.customer,
            order_fields={
                "shipping_full_name": "Jane Doe", "shipping_phone": "0300-1234567",
                "shipping_address_line": "123 Main St", "shipping_city": "Karachi",
                "shipping_state": "", "shipping_postal_code": "", "shipping_country": "Pakistan",
                "billing_same_as_shipping": True, "billing_full_name": "", "billing_phone": "",
                "billing_address_line": "", "billing_city": "", "billing_state": "",
                "billing_postal_code": "", "billing_country": "",
                "payment_method": payment_method, "coupon_code": "",
                "shipping_cost": 0, "tax_amount": 0,
            },
        )
        return orders[0]


@override_settings(
    JAZZCASH_MERCHANT_ID="MC12345", JAZZCASH_PASSWORD="pwd123", JAZZCASH_INTEGRITY_SALT="salt123",
    JAZZCASH_RETURN_URL="http://testserver/api/payments/callbacks/jazzcash/",
)
class JazzCashIntegrationTests(RedirectGatewayTestBase):
    def test_checkout_returns_signed_redirect_fields(self):
        response = self._checkout("jazzcash")
        self.assertEqual(response.status_code, 201)
        self.assertIn("checkout_url", response.data)
        fields = response.data["fields"]
        self.assertEqual(fields["pp_Amount"], "2000")  # $20.00 -> paisas
        self.assertTrue(fields["pp_SecureHash"])

        order = Order.objects.get(order_number=response.data["orders"][0]["order_number"])
        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.method, "jazzcash")
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.reference, fields["pp_TxnRefNo"])

    def _signed_callback(self, txn_ref, response_code, **extra):
        # A genuine JazzCash callback carries JazzCash's OWN pp_SecureHash over the response
        # fields (distinct from the hash we sent on the outbound request) — reusing our
        # request's hash here would test the wrong thing, so we sign the response fields the
        # same way our verify_callback recomputes them, standing in for "JazzCash signed this".
        fields = {"pp_TxnRefNo": txn_ref, "pp_ResponseCode": response_code, "pp_Amount": "2000", **extra}
        fields["pp_SecureHash"] = jazzcash_gateway._compute_secure_hash(fields)
        return fields

    def test_callback_with_valid_hash_and_success_code_confirms_order(self):
        order = self._place_order_directly("jazzcash")
        request = jazzcash_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["pp_TxnRefNo"], "000")

        orders = jazzcash_gateway.handle_callback(callback_data)
        self.assertEqual(len(orders), 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.status, Order.Status.PROCESSING)

    def test_callback_with_failure_code_marks_order_failed(self):
        order = self._place_order_directly("jazzcash")
        request = jazzcash_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["pp_TxnRefNo"], "134")  # non-success code

        jazzcash_gateway.handle_callback(callback_data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_tampered_callback_hash_is_rejected(self):
        order = self._place_order_directly("jazzcash")
        request = jazzcash_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["pp_TxnRefNo"], "000")
        callback_data["pp_Amount"] = "1"  # tampered after signing

        with self.assertRaises(ValueError):
            jazzcash_gateway.handle_callback(callback_data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_callback_view_rejects_bad_signature(self):
        response = self.client.post(
            reverse("payments_api:jazzcash-callback"),
            {"pp_TxnRefNo": "T123", "pp_ResponseCode": "000", "pp_SecureHash": "not-a-real-hash"},
        )
        self.assertEqual(response.status_code, 400)

    def test_refund_not_implemented(self):
        order = self._place_order_directly("jazzcash")
        with self.assertRaises(NotImplementedError):
            jazzcash_gateway.refund(order)


@override_settings(
    EASYPAISA_STORE_ID="12345", EASYPAISA_HASH_KEY="hashkey123",
    EASYPAISA_RETURN_URL="http://testserver/api/payments/callbacks/easypaisa/",
)
class EasyPaisaIntegrationTests(RedirectGatewayTestBase):
    def test_checkout_returns_signed_redirect_fields(self):
        response = self._checkout("easypaisa")
        self.assertEqual(response.status_code, 201)
        self.assertIn("checkout_url", response.data)
        fields = response.data["fields"]
        self.assertEqual(fields["amount"], "20.00")
        self.assertTrue(fields["merchantHashedReq"])

        order = Order.objects.get(order_number=response.data["orders"][0]["order_number"])
        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.method, "easypaisa")
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.reference, fields["orderRefNum"])

    def _signed_callback(self, order_ref, status, **extra):
        # A genuine EasyPaisa callback carries EasyPaisa's OWN hash over the response fields
        # (distinct from the hash we sent on the outbound request) — reusing our request's
        # hash here would test the wrong thing, so we sign the response fields the same way
        # our verify_callback recomputes them, standing in for "EasyPaisa signed this".
        fields = {"orderRefNum": order_ref, "status": status, "amount": "20.00", **extra}
        fields["merchantHashedReq"] = easypaisa_gateway._compute_hash(fields)
        return fields

    def test_callback_with_valid_hash_and_success_status_confirms_order(self):
        order = self._place_order_directly("easypaisa")
        request = easypaisa_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["orderRefNum"], "0000")

        orders = easypaisa_gateway.handle_callback(callback_data)
        self.assertEqual(len(orders), 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.status, Order.Status.PROCESSING)

    def test_callback_with_failure_status_marks_order_failed(self):
        order = self._place_order_directly("easypaisa")
        request = easypaisa_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["orderRefNum"], "0001")

        easypaisa_gateway.handle_callback(callback_data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_tampered_callback_hash_is_rejected(self):
        order = self._place_order_directly("easypaisa")
        request = easypaisa_gateway.build_payment_request([order])
        callback_data = self._signed_callback(request["fields"]["orderRefNum"], "0000")
        callback_data["amount"] = "1.00"  # tampered after signing

        with self.assertRaises(ValueError):
            easypaisa_gateway.handle_callback(callback_data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_callback_view_rejects_bad_signature(self):
        response = self.client.post(
            reverse("payments_api:easypaisa-callback"),
            {"orderRefNum": "E123", "status": "0000", "merchantHashedReq": "not-a-real-hash"},
        )
        self.assertEqual(response.status_code, 400)

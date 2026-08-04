"""Stripe gateway: Customer, PaymentIntent, webhook verification, refund.

Flow: CheckoutView creates the Order(s) (pending, unpaid) via orders.services.place_order,
then calls create_payment_intent_for_orders() here to get a client_secret for the frontend
to confirm with Stripe.js. The order is only marked paid — and only then moved out of
PENDING — once Stripe's webhook confirms the charge via handle_webhook_event(); the
frontend's "payment succeeded" response is never trusted on its own.
"""

from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from django.db import transaction

from apps.notifications import services as notification_services
from apps.orders import services as orders_services
from apps.orders.models import Order

from ..models import PaymentTransaction, StripeCustomer
from . import record_payment, save_payment_method

ZERO_DECIMAL_CURRENCIES = {"jpy", "krw"}  # currencies Stripe expects as whole units, not cents


def _client():
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _to_smallest_unit(amount: Decimal, currency: str) -> int:
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def get_or_create_customer(user):
    client = _client()
    existing = StripeCustomer.objects.filter(user=user).first()
    if existing is not None:
        return existing
    customer = client.Customer.create(email=user.email, name=user.get_full_name())
    return StripeCustomer.objects.create(user=user, stripe_customer_id=customer.id)


@transaction.atomic
def create_payment_intent_for_orders(orders, user):
    """One PaymentIntent covers the whole checkout (which may span multiple per-vendor
    Orders); each Order gets its own PENDING PaymentTransaction referencing that intent."""
    client = _client()
    stripe_customer = get_or_create_customer(user)
    currency = settings.STRIPE_CURRENCY
    total = sum((order.total_amount for order in orders), Decimal("0"))

    intent = client.PaymentIntent.create(
        amount=_to_smallest_unit(total, currency),
        currency=currency,
        customer=stripe_customer.stripe_customer_id,
        metadata={"order_numbers": ",".join(order.order_number for order in orders)},
        automatic_payment_methods={"enabled": True},
    )
    for order in orders:
        record_payment(
            order,
            method="stripe",
            amount=order.total_amount,
            status=PaymentTransaction.Status.PENDING,
            reference=intent.id,
        )
    return intent


def create_setup_intent(user):
    """Starts the flow for saving a new card: the frontend collects card details with
    Stripe.js/Elements against this intent's client_secret, without the card ever touching
    our servers, then confirms and calls attach_payment_method() with the resulting PM id."""
    client = _client()
    stripe_customer = get_or_create_customer(user)
    return client.SetupIntent.create(
        customer=stripe_customer.stripe_customer_id, automatic_payment_methods={"enabled": True}
    )


def attach_payment_method(user, payment_method_id, *, is_default=False):
    client = _client()
    stripe_customer = get_or_create_customer(user)
    payment_method = client.PaymentMethod.retrieve(payment_method_id)
    if payment_method.customer != stripe_customer.stripe_customer_id:
        client.PaymentMethod.attach(payment_method_id, customer=stripe_customer.stripe_customer_id)

    card = payment_method.card
    return save_payment_method(
        user,
        provider="stripe",
        provider_customer_id=stripe_customer.stripe_customer_id,
        provider_payment_method_id=payment_method_id,
        card_brand=card.brand,
        card_last4=card.last4,
        card_exp_month=card.exp_month,
        card_exp_year=card.exp_year,
        is_default=is_default,
    )


def construct_webhook_event(payload, sig_header):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured.")
    return stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


@transaction.atomic
def _finalize_payment_intent(intent_id, *, succeeded):
    pending = PaymentTransaction.objects.select_for_update().filter(
        reference=intent_id, method="stripe", status=PaymentTransaction.Status.PENDING
    )
    for txn in pending:
        txn.status = PaymentTransaction.Status.SUCCESS if succeeded else PaymentTransaction.Status.FAILED
        txn.save(update_fields=["status"])

        order = Order.objects.select_for_update().get(pk=txn.order_id)
        order.payment_status = Order.PaymentStatus.PAID if succeeded else Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status"])

        if succeeded and order.status == Order.Status.PENDING:
            orders_services.transition_status(
                order, Order.Status.PROCESSING, note="Payment confirmed via Stripe webhook"
            )
        else:
            notification_services.notify(
                order.customer,
                title=f"Payment {'confirmed' if succeeded else 'failed'} for {order.order_number}",
                message="" if succeeded else "Your card was declined. Please try again or use another payment method.",
                notification_type="order_update",
            )


def handle_webhook_event(event):
    event_type = event["type"]
    intent = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        _finalize_payment_intent(intent["id"], succeeded=True)
    elif event_type == "payment_intent.payment_failed":
        _finalize_payment_intent(intent["id"], succeeded=False)
    # Other event types (e.g. charge.refunded) are ignored here; refunds initiated by us
    # are recorded synchronously by refund_payment_intent() below.


@transaction.atomic
def refund_payment_intent(order):
    client = _client()
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.payment_status == Order.PaymentStatus.REFUNDED:
        raise ValueError(f"Order {order.order_number} has already been refunded.")

    paid_txn = (
        PaymentTransaction.objects.filter(
            order=order, method="stripe", status=PaymentTransaction.Status.SUCCESS
        )
        .order_by("-created_at")
        .first()
    )
    if paid_txn is None:
        raise ValueError(f"Order {order.order_number} has no successful Stripe payment to refund.")

    refund = client.Refund.create(payment_intent=paid_txn.reference)

    PaymentTransaction.objects.create(
        order=order,
        method="stripe_refund",
        amount=order.total_amount,
        status=PaymentTransaction.Status.REFUNDED,
        reference=refund.id,
    )
    order.payment_status = Order.PaymentStatus.REFUNDED
    order.save(update_fields=["payment_status"])
    return order

"""EasyPaisa hosted checkout redirect flow.

Flow: build_payment_request() returns a checkout_url + signed form fields; the frontend
auto-submits a hidden form with those fields (POST) to checkout_url, the customer completes
payment on EasyPaisa's page, and EasyPaisa POSTs back to EASYPAISA_RETURN_URL with the
result. We only trust that callback after re-computing merchantHashedReq ourselves and
confirming it matches (verify_callback) — never the browser redirect alone.

NOTE: this follows EasyPaisa's standard documented hosted-checkout shape (storeId + a
SHA-256 hash of the sorted request fields keyed by your Hash Key). Field names and the
success/failure status code should be double-checked against your EasyPaisa merchant
integration guide before going live — this wasn't verified against a live sandbox.
"""

import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications import services as notification_services
from apps.orders import services as orders_services
from apps.orders.models import Order

from ..models import PaymentTransaction
from . import record_payment

SANDBOX_URL = "https://easypaystg.easypaisa.com.pk/easypay/Index.jsf"
PRODUCTION_URL = "https://easypay.easypaisa.com.pk/easypay/Index.jsf"

SUCCESS_STATUS = "0000"


def _checkout_url():
    return PRODUCTION_URL if settings.EASYPAISA_ENVIRONMENT == "production" else SANDBOX_URL


def _require_config():
    if not (settings.EASYPAISA_STORE_ID and settings.EASYPAISA_HASH_KEY):
        raise RuntimeError("EasyPaisa credentials are not configured.")


def _compute_hash(fields):
    sorted_pairs = "&".join(f"{key}={fields[key]}" for key in sorted(fields) if fields.get(key) not in (None, ""))
    message = f"{sorted_pairs}&hashKey={settings.EASYPAISA_HASH_KEY}"
    return hashlib.sha256(message.encode()).hexdigest()


def build_payment_request(orders):
    """One EasyPaisa transaction covers the whole checkout (which may span multiple
    per-vendor Orders); each Order gets its own PENDING PaymentTransaction referencing it."""
    _require_config()
    now = timezone.now()
    total = sum((order.total_amount for order in orders), Decimal("0"))
    order_ref = f"E{now.strftime('%Y%m%d%H%M%S')}{orders[0].id}"

    fields = {
        "storeId": settings.EASYPAISA_STORE_ID,
        "amount": str(total),
        "postBackURL": settings.EASYPAISA_RETURN_URL,
        "orderRefNum": order_ref,
        "expiryDate": (now + timedelta(days=1)).strftime("%Y%m%d %H%M%S"),
        "paymentMethod": "InstaPay",
        "autoRedirect": "1",
    }
    fields["merchantHashedReq"] = _compute_hash(fields)

    for order in orders:
        record_payment(
            order, method="easypaisa", amount=order.total_amount,
            status=PaymentTransaction.Status.PENDING, reference=order_ref,
        )
    return {"checkout_url": _checkout_url(), "fields": fields}


def verify_callback(data):
    received_hash = data.get("merchantHashedReq", "")
    fields = {key: value for key, value in data.items() if key != "merchantHashedReq"}
    expected_hash = _compute_hash(fields)
    return bool(received_hash) and hmac.compare_digest(received_hash, expected_hash)


@transaction.atomic
def handle_callback(data):
    if not verify_callback(data):
        raise ValueError("Invalid EasyPaisa hash — callback rejected.")

    order_ref = data.get("orderRefNum", "")
    succeeded = data.get("status") == SUCCESS_STATUS

    pending = PaymentTransaction.objects.select_for_update().filter(
        reference=order_ref, method="easypaisa", status=PaymentTransaction.Status.PENDING
    )
    updated_orders = []
    for txn in pending:
        txn.status = PaymentTransaction.Status.SUCCESS if succeeded else PaymentTransaction.Status.FAILED
        txn.save(update_fields=["status"])

        order = Order.objects.select_for_update().get(pk=txn.order_id)
        order.payment_status = Order.PaymentStatus.PAID if succeeded else Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status"])

        if succeeded and order.status == Order.Status.PENDING:
            orders_services.transition_status(
                order, Order.Status.PROCESSING, note="Payment confirmed via EasyPaisa callback"
            )
        else:
            notification_services.notify(
                order.customer,
                title=f"Payment {'confirmed' if succeeded else 'failed'} for {order.order_number}",
                message="" if succeeded else "Your EasyPaisa payment failed. Please try again.",
                notification_type="order_update",
            )
        updated_orders.append(order)
    return updated_orders

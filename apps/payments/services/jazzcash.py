"""JazzCash Mobile Wallet / hosted "Page-Post" checkout redirect flow.

Flow: build_payment_request() returns a checkout_url + signed form fields; the frontend
auto-submits a hidden form with those fields (POST) to checkout_url, the customer completes
payment on JazzCash's page, and JazzCash POSTs back to JAZZCASH_RETURN_URL with the result.
We only trust that callback after re-computing pp_SecureHash ourselves and confirming it
matches (verify_callback) — never the browser redirect alone.

NOTE: this follows JazzCash's standard documented Page-Post shape (pp_-prefixed fields,
HMAC-SHA256 of the sorted field values keyed by your Integrity Salt). Field names and the
exact hash concatenation order should be double-checked against the current Integration
Guide PDF in your JazzCash merchant dashboard before going live — gateway API versions do
shift over time and this wasn't verified against a live sandbox.
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

SANDBOX_URL = "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/"
PRODUCTION_URL = "https://payments.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/"

SUCCESS_RESPONSE_CODE = "000"


def _checkout_url():
    return PRODUCTION_URL if settings.JAZZCASH_ENVIRONMENT == "production" else SANDBOX_URL


def _require_config():
    if not (settings.JAZZCASH_MERCHANT_ID and settings.JAZZCASH_PASSWORD and settings.JAZZCASH_INTEGRITY_SALT):
        raise RuntimeError("JazzCash credentials are not configured.")


def _compute_secure_hash(fields):
    salt = settings.JAZZCASH_INTEGRITY_SALT
    sorted_values = [str(fields[key]) for key in sorted(fields) if fields.get(key) not in (None, "")]
    message = "&".join([salt] + sorted_values)
    return hmac.new(salt.encode(), message.encode(), hashlib.sha256).hexdigest().upper()


def build_payment_request(orders):
    """One JazzCash transaction covers the whole checkout (which may span multiple
    per-vendor Orders); each Order gets its own PENDING PaymentTransaction referencing it."""
    _require_config()
    now = timezone.now()
    total = sum((order.total_amount for order in orders), Decimal("0"))
    txn_ref = f"T{now.strftime('%Y%m%d%H%M%S')}{orders[0].id}"

    fields = {
        "pp_Version": "1.1",
        "pp_TxnType": "MWALLET",
        "pp_Language": "EN",
        "pp_MerchantID": settings.JAZZCASH_MERCHANT_ID,
        "pp_Password": settings.JAZZCASH_PASSWORD,
        "pp_TxnRefNo": txn_ref,
        "pp_Amount": str(int((total * 100).to_integral_value())),  # paisas
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": now.strftime("%Y%m%d%H%M%S"),
        "pp_TxnExpiryDateTime": (now + timedelta(days=1)).strftime("%Y%m%d%H%M%S"),
        "pp_BillReference": orders[0].order_number,
        "pp_Description": f"FaizanMart order {orders[0].order_number}",
        "pp_ReturnURL": settings.JAZZCASH_RETURN_URL,
    }
    fields["pp_SecureHash"] = _compute_secure_hash(fields)

    for order in orders:
        record_payment(
            order, method="jazzcash", amount=order.total_amount,
            status=PaymentTransaction.Status.PENDING, reference=txn_ref,
        )
    return {"checkout_url": _checkout_url(), "fields": fields}


def verify_callback(data):
    received_hash = data.get("pp_SecureHash", "")
    fields = {key: value for key, value in data.items() if key.startswith("pp_") and key != "pp_SecureHash"}
    expected_hash = _compute_secure_hash(fields)
    return bool(received_hash) and hmac.compare_digest(received_hash, expected_hash)


@transaction.atomic
def handle_callback(data):
    if not verify_callback(data):
        raise ValueError("Invalid JazzCash secure hash — callback rejected.")

    txn_ref = data.get("pp_TxnRefNo", "")
    succeeded = data.get("pp_ResponseCode") == SUCCESS_RESPONSE_CODE

    pending = PaymentTransaction.objects.select_for_update().filter(
        reference=txn_ref, method="jazzcash", status=PaymentTransaction.Status.PENDING
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
                order, Order.Status.PROCESSING, note="Payment confirmed via JazzCash callback"
            )
        else:
            notification_services.notify(
                order.customer,
                title=f"Payment {'confirmed' if succeeded else 'failed'} for {order.order_number}",
                message="" if succeeded else "Your JazzCash payment failed. Please try again.",
                notification_type="order_update",
            )
        updated_orders.append(order)
    return updated_orders


def refund(order):
    # JazzCash refunds go through a separate Refund/Reversal API that must be explicitly
    # enabled for your merchant account; process via the JazzCash merchant portal until
    # that's set up, or implement this once you have Refund API credentials.
    raise NotImplementedError("JazzCash refunds are not enabled for this merchant account yet.")

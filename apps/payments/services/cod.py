"""Cash on Delivery: no upfront gateway call. Payment is collected by the delivery boy and
marked paid manually by staff (see orders.transition / a future delivery-confirmation step)."""

from ..models import PaymentTransaction
from . import record_payment


def initiate(order):
    return record_payment(order, method="cod", amount=order.total_amount, status=PaymentTransaction.Status.PENDING)

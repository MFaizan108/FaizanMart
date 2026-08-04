from django.db import transaction

from apps.orders.models import Order

from ..models import PaymentTransaction, SavedPaymentMethod, Wallet, WalletTransaction


def get_or_create_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def credit_wallet(user, amount, reason="", order=None):
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=WalletTransaction.Type.CREDIT,
            amount=amount,
            balance_after=wallet.balance,
            reason=reason,
            order=order,
        )
    return wallet


def debit_wallet(user, amount, reason="", order=None):
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get_or_create(user=user)[0]
        if wallet.balance < amount:
            raise ValueError("Insufficient wallet balance.")
        wallet.balance -= amount
        wallet.save(update_fields=["balance", "updated_at"])
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type=WalletTransaction.Type.DEBIT,
            amount=amount,
            balance_after=wallet.balance,
            reason=reason,
            order=order,
        )
    return wallet


def refund_order_to_wallet(order):
    """Refunds an order's total_amount to the customer's wallet (used regardless of original
    payment method, since we don't have real gateway refund APIs to call)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == Order.PaymentStatus.REFUNDED:
            raise ValueError(f"Order {order.order_number} has already been refunded.")
        credit_wallet(order.customer, order.total_amount, reason=f"Refund for {order.order_number}", order=order)
        PaymentTransaction.objects.create(
            order=order,
            method="wallet_refund",
            amount=order.total_amount,
            status=PaymentTransaction.Status.REFUNDED,
        )
        order.payment_status = Order.PaymentStatus.REFUNDED
        order.save(update_fields=["payment_status"])
    return order


def record_payment(order, method, amount, status=PaymentTransaction.Status.SUCCESS, reference=""):
    return PaymentTransaction.objects.create(
        order=order, method=method, amount=amount, status=status, reference=reference
    )


@transaction.atomic
def save_payment_method(user, *, is_default=False, **fields):
    """Records a reference to a payment method already created with the provider
    (e.g. after a Stripe SetupIntent confirms). Never pass raw card data in `fields`."""
    is_first = not SavedPaymentMethod.objects.filter(user=user).exists()
    if is_first:
        is_default = True
    if is_default:
        SavedPaymentMethod.objects.filter(user=user, is_default=True).update(is_default=False)
    return SavedPaymentMethod.objects.create(user=user, is_default=is_default, **fields)


@transaction.atomic
def set_default_payment_method(payment_method):
    SavedPaymentMethod.objects.filter(user=payment_method.user, is_default=True).update(is_default=False)
    payment_method.is_default = True
    payment_method.save(update_fields=["is_default"])
    return payment_method


@transaction.atomic
def delete_payment_method(payment_method):
    user = payment_method.user
    was_default = payment_method.is_default
    payment_method.delete()
    if was_default:
        replacement = SavedPaymentMethod.objects.filter(user=user).order_by("-created_at").first()
        if replacement is not None:
            replacement.is_default = True
            replacement.save(update_fields=["is_default"])

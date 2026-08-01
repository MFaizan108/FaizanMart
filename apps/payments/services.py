from django.db import transaction

from .models import PaymentTransaction, Wallet, WalletTransaction


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
        credit_wallet(order.customer, order.total_amount, reason=f"Refund for {order.order_number}", order=order)
        PaymentTransaction.objects.create(
            order=order,
            method="wallet_refund",
            amount=order.total_amount,
            status=PaymentTransaction.Status.REFUNDED,
        )


def record_payment(order, method, amount, status=PaymentTransaction.Status.SUCCESS, reference=""):
    return PaymentTransaction.objects.create(
        order=order, method=method, amount=amount, status=status, reference=reference
    )

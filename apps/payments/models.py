from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Wallet(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Wallet({self.user.email}): {self.balance}"


class WalletTransaction(models.Model):
    class Type(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.wallet.user.email}: {self.transaction_type} {self.amount}"


class SavedPaymentMethod(TimeStampedModel):
    """A reference to a payment method held by an external provider (e.g. Stripe).

    We never store real card numbers/CVVs here — only the provider's customer/payment-method
    IDs plus non-sensitive display metadata (brand/last4/expiry) the provider's API returns.
    """

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_payment_methods"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices, default=Provider.STRIPE)
    provider_customer_id = models.CharField(max_length=255)
    provider_payment_method_id = models.CharField(max_length=255, unique=True)
    card_brand = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    card_exp_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        indexes = [models.Index(fields=["user"])]

    def __str__(self):
        return f"{self.provider}:{self.card_brand} ****{self.card_last4} ({self.user.email})"


class StripeCustomer(TimeStampedModel):
    """Maps a FaizanMart user to their Stripe Customer object (one per user, reused across
    every card they save/charge). Never stores card data — just the provider reference."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stripe_customer"
    )
    stripe_customer_id = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return f"{self.user.email}: {self.stripe_customer_id}"


class PaymentTransaction(models.Model):
    """Records an attempted/completed payment capture for an order, regardless of method."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payment_transactions")
    method = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order.order_number}: {self.method} {self.status}"

from decimal import Decimal

from rest_framework import serializers

from .models import PaymentTransaction, SavedPaymentMethod, Wallet, WalletTransaction


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["id", "balance", "created_at", "updated_at"]
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ["id", "transaction_type", "amount", "balance_after", "reason", "order", "created_at"]
        read_only_fields = fields


class AddMoneySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(required=False, allow_blank=True, default="Wallet top-up")


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = ["id", "order", "method", "amount", "status", "reference", "created_at"]
        read_only_fields = fields


class AttachPaymentMethodSerializer(serializers.Serializer):
    payment_method_id = serializers.CharField()
    is_default = serializers.BooleanField(default=False)


class SavedPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPaymentMethod
        fields = [
            "id",
            "provider",
            "card_brand",
            "card_last4",
            "card_exp_month",
            "card_exp_year",
            "is_default",
            "created_at",
        ]
        read_only_fields = fields

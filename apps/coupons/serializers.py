from decimal import Decimal

from rest_framework import serializers

from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "discount_type",
            "value",
            "store",
            "usage_limit",
            "used_count",
            "per_customer_limit",
            "min_order_amount",
            "valid_from",
            "valid_until",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "used_count", "created_at"]


class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))

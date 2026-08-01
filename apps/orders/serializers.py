from decimal import Decimal

from rest_framework import serializers

from .models import Order, OrderItem, OrderStatusHistory


class CheckoutSerializer(serializers.Serializer):
    shipping_full_name = serializers.CharField(max_length=150)
    shipping_phone = serializers.CharField(max_length=20)
    shipping_address_line = serializers.CharField(max_length=255)
    shipping_city = serializers.CharField(max_length=100)
    shipping_state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    shipping_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    shipping_country = serializers.CharField(max_length=100)

    billing_same_as_shipping = serializers.BooleanField(default=True)
    billing_full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    billing_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    billing_address_line = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    billing_city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    billing_state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    billing_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    billing_country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    coupon_code = serializers.CharField(required=False, allow_blank=True, default="")
    shipping_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )
    tax_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )

    def validate(self, attrs):
        if not attrs.get("billing_same_as_shipping", True):
            required = [
                "billing_full_name",
                "billing_phone",
                "billing_address_line",
                "billing_city",
                "billing_country",
            ]
            missing = [field for field in required if not attrs.get(field)]
            if missing:
                raise serializers.ValidationError(
                    f"Billing address required when billing_same_as_shipping is false: {', '.join(missing)}"
                )
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "variant",
            "warehouse",
            "product_name",
            "sku",
            "unit_price",
            "quantity",
            "line_total",
        ]
        read_only_fields = fields


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ["id", "status", "note", "changed_by", "created_at"]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer_email",
            "store",
            "store_name",
            "status",
            "payment_method",
            "payment_status",
            "shipping_full_name",
            "shipping_phone",
            "shipping_address_line",
            "shipping_city",
            "shipping_state",
            "shipping_postal_code",
            "shipping_country",
            "billing_same_as_shipping",
            "billing_full_name",
            "billing_phone",
            "billing_address_line",
            "billing_city",
            "billing_state",
            "billing_postal_code",
            "billing_country",
            "subtotal",
            "discount_amount",
            "tax_amount",
            "shipping_cost",
            "total_amount",
            "cancelled_at",
            "cancel_reason",
            "items",
            "status_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")

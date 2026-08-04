from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import Address

from .models import Order, OrderItem, OrderStatusHistory


def _address_to_fields(address, prefix):
    line = address.address_line1
    if address.address_line2:
        line = f"{line}, {address.address_line2}"
    return {
        f"{prefix}_full_name": address.full_name,
        f"{prefix}_phone": address.phone_number,
        f"{prefix}_address_line": line,
        f"{prefix}_city": address.city,
        f"{prefix}_state": address.state,
        f"{prefix}_postal_code": address.postal_code,
        f"{prefix}_country": address.country,
    }


class CheckoutSerializer(serializers.Serializer):
    # Either pass a saved address id, or the flat fields directly (e.g. for a one-off address).
    shipping_address_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    shipping_full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    shipping_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    shipping_address_line = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    shipping_city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    shipping_state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    shipping_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    shipping_country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    billing_same_as_shipping = serializers.BooleanField(default=True)
    billing_address_id = serializers.IntegerField(required=False, allow_null=True, default=None)
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
    # shipping_cost is intentionally not a field here — it's computed server-side by the
    # shipping rules engine (apps.shipping.rules.calculate_shipping_cost) in place_order(),
    # never trusted from the client. Use the shipping quote endpoint to preview it first.
    tax_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )

    def _resolve_address(self, address_id, field_name):
        user = self.context["request"].user
        address = Address.objects.filter(pk=address_id, user=user).first()
        if address is None:
            raise serializers.ValidationError({field_name: "Address not found."})
        return address

    def validate(self, attrs):
        shipping_address_id = attrs.pop("shipping_address_id", None)
        if shipping_address_id is not None:
            address = self._resolve_address(shipping_address_id, "shipping_address_id")
            attrs.update(_address_to_fields(address, "shipping"))

        required_shipping = [
            "shipping_full_name",
            "shipping_phone",
            "shipping_address_line",
            "shipping_city",
            "shipping_country",
        ]
        missing = [field for field in required_shipping if not attrs.get(field)]
        if missing:
            raise serializers.ValidationError(
                f"Shipping address required (pass shipping_address_id or these fields): {', '.join(missing)}"
            )

        billing_address_id = attrs.pop("billing_address_id", None)
        if not attrs.get("billing_same_as_shipping", True):
            if billing_address_id is not None:
                address = self._resolve_address(billing_address_id, "billing_address_id")
                attrs.update(_address_to_fields(address, "billing"))

            required_billing = [
                "billing_full_name",
                "billing_phone",
                "billing_address_line",
                "billing_city",
                "billing_country",
            ]
            missing = [field for field in required_billing if not attrs.get(field)]
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

from rest_framework import serializers

from apps.accounts.models import User
from apps.orders.models import Order

from .models import Courier, DeliveryAssignment, Shipment, ShippingRule


class ShippingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRule
        fields = [
            "id",
            "name",
            "is_active",
            "priority",
            "country",
            "province",
            "city",
            "store",
            "warehouse",
            "min_weight",
            "max_weight",
            "min_order_amount",
            "max_order_amount",
            "shipping_cost",
            "is_free_shipping",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ShippingQuoteSerializer(serializers.Serializer):
    country = serializers.CharField()
    province = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(required=False, allow_blank=True, default="")
    store = serializers.IntegerField(required=False, allow_null=True, default=None)
    weight = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, default=0)
    order_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0)


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    delivery_boy_email = serializers.EmailField(source="delivery_boy.email", read_only=True)

    class Meta:
        model = DeliveryAssignment
        fields = [
            "id",
            "order",
            "order_number",
            "delivery_boy",
            "delivery_boy_email",
            "status",
            "assigned_at",
            "picked_up_at",
            "out_for_delivery_at",
            "delivered_at",
            "failed_at",
            "failure_reason",
        ]
        read_only_fields = [
            "id", "status", "assigned_at", "picked_up_at", "out_for_delivery_at",
            "delivered_at", "failed_at", "failure_reason",
        ]


class DeliveryAssignCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    delivery_boy = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="delivery_boy"))


class DeliveryStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DeliveryAssignment.Status.choices)
    failure_reason = serializers.CharField(required=False, allow_blank=True, default="")


class CourierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Courier
        fields = ["id", "name", "tracking_url_template", "is_active"]
        read_only_fields = ["id"]


class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    courier_name = serializers.CharField(source="courier.name", read_only=True)
    tracking_url = serializers.CharField(read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id",
            "order",
            "order_number",
            "courier",
            "courier_name",
            "tracking_number",
            "status",
            "tracking_url",
            "shipped_at",
            "delivered_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "shipped_at", "delivered_at", "created_at"]


class ShipmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Shipment.Status.choices)

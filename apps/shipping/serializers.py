from rest_framework import serializers

from .models import Courier, Shipment


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

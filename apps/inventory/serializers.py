from rest_framework import serializers

from .models import InventoryLog, Stock, StockTransfer, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "name",
            "code",
            "address_line",
            "city",
            "state",
            "postal_code",
            "country",
            "manager",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse",
            "warehouse_name",
            "quantity",
            "reserved_quantity",
            "available_quantity",
            "low_stock_threshold",
            "is_low_stock",
            "is_out_of_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "quantity", "reserved_quantity", "created_at", "updated_at"]


class RestockActionSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class AdjustActionSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ReserveReleaseActionSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class StockTransferSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = StockTransfer
        fields = [
            "id",
            "product",
            "product_name",
            "from_warehouse",
            "to_warehouse",
            "quantity",
            "status",
            "requested_by",
            "completed_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "requested_by", "completed_at", "created_at"]


class InventoryLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = InventoryLog
        fields = [
            "id",
            "product",
            "product_name",
            "warehouse",
            "warehouse_code",
            "change_type",
            "quantity_delta",
            "reserved_delta",
            "resulting_quantity",
            "resulting_reserved_quantity",
            "note",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

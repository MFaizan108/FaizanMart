from django.contrib import admin

from .models import InventoryLog, Stock, StockTransfer, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "manager", "is_active"]
    search_fields = ["name", "code"]
    list_filter = ["is_active"]


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ["product", "warehouse", "quantity", "reserved_quantity", "low_stock_threshold"]
    list_filter = ["warehouse"]
    search_fields = ["product__name", "warehouse__code"]
    readonly_fields = ["quantity", "reserved_quantity"]


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ["product", "from_warehouse", "to_warehouse", "quantity", "status", "created_at"]
    list_filter = ["status"]
    readonly_fields = ["requested_by", "completed_at"]


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ["product", "warehouse", "change_type", "quantity_delta", "reserved_delta", "created_at"]
    list_filter = ["change_type"]
    readonly_fields = [f.name for f in InventoryLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

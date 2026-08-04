from django.contrib import admin

from .models import Courier, DeliveryAssignment, Shipment, ShippingRule


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ["order", "courier", "tracking_number", "status", "shipped_at", "delivered_at"]
    list_filter = ["status", "courier"]
    search_fields = ["order__order_number", "tracking_number"]


@admin.register(ShippingRule)
class ShippingRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "priority", "country", "province", "city", "shipping_cost", "is_free_shipping"]
    list_filter = ["is_active", "is_free_shipping", "country"]
    search_fields = ["name", "city", "province", "country"]


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ["order", "delivery_boy", "status", "assigned_at", "delivered_at"]
    list_filter = ["status"]
    search_fields = ["order__order_number", "delivery_boy__email"]
    readonly_fields = [f.name for f in DeliveryAssignment._meta.fields]

    def has_add_permission(self, request):
        return False

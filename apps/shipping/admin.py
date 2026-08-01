from django.contrib import admin

from .models import Courier, Shipment


@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ["order", "courier", "tracking_number", "status", "shipped_at", "delivered_at"]
    list_filter = ["status", "courier"]
    search_fields = ["order__order_number", "tracking_number"]

from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, ReturnRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [f.name for f in OrderItem._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = [f.name for f in OrderStatusHistory._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "customer", "store", "status", "payment_method", "total_amount", "created_at"]
    list_filter = ["status", "payment_method", "payment_status"]
    search_fields = ["order_number", "customer__email", "store__name"]
    readonly_fields = [f.name for f in Order._meta.fields]
    inlines = [OrderItemInline, OrderStatusHistoryInline]

    def has_add_permission(self, request):
        return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ["order", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["order__order_number", "order__customer__email"]

    def has_add_permission(self, request):
        return False

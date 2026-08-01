from django.contrib import admin

from .models import FAQ, Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ["sender", "message", "created_at"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "customer", "status", "priority", "assigned_to", "created_at"]
    list_filter = ["status", "priority"]
    search_fields = ["subject", "customer__email"]
    inlines = [TicketMessageInline]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "category", "sort_order", "is_published"]
    list_filter = ["category", "is_published"]

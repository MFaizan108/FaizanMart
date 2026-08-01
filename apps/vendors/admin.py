from django.contrib import admin

from . import services
from .models import Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name", "owner__email"]
    readonly_fields = ["slug", "approved_at", "approved_by", "created_at", "updated_at"]
    actions = ["approve_selected", "reject_selected"]

    @admin.action(description="Approve selected stores")
    def approve_selected(self, request, queryset):
        for store in queryset:
            services.approve_store(store, request.user)

    @admin.action(description="Reject selected stores")
    def reject_selected(self, request, queryset):
        for store in queryset:
            services.reject_store(store, request.user, "Rejected via admin bulk action.")

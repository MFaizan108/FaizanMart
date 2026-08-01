from django.contrib import admin

from .models import PaymentTransaction, Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "balance", "updated_at"]
    search_fields = ["user__email"]
    readonly_fields = ["balance"]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ["wallet", "transaction_type", "amount", "balance_after", "created_at"]
    list_filter = ["transaction_type"]
    readonly_fields = [f.name for f in WalletTransaction._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["order", "method", "amount", "status", "created_at"]
    list_filter = ["method", "status"]
    readonly_fields = [f.name for f in PaymentTransaction._meta.fields]

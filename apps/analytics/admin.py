from django.contrib import admin

from .models import ProductView


@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "viewed_at"]
    list_filter = ["viewed_at"]
    search_fields = ["product__name", "user__email"]

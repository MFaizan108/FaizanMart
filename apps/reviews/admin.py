from django.contrib import admin

from .models import Review, ReviewImage, WishlistItem


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "customer", "rating", "is_verified_purchase", "created_at"]
    list_filter = ["rating", "is_verified_purchase"]
    search_fields = ["product__name", "customer__email"]
    inlines = [ReviewImageInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ["customer", "product", "created_at"]
    search_fields = ["customer__email", "product__name"]

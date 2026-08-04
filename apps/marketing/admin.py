from django.contrib import admin

from .models import (
    Banner,
    FeaturedProduct,
    FlashSale,
    FlashSaleItem,
    NewsletterSubscriber,
    ReferralCode,
    ReferralSignup,
)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ["title", "position", "sort_order", "is_active"]
    list_filter = ["position", "is_active"]


@admin.register(FeaturedProduct)
class FeaturedProductAdmin(admin.ModelAdmin):
    list_display = ["product", "sort_order", "featured_at"]


class FlashSaleItemInline(admin.TabularInline):
    model = FlashSaleItem
    extra = 0


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ["name", "starts_at", "ends_at", "is_active"]
    inlines = [FlashSaleItemInline]


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "is_active", "subscribed_at"]
    search_fields = ["email"]


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ["user", "code", "created_at"]
    search_fields = ["code", "user__email"]


@admin.register(ReferralSignup)
class ReferralSignupAdmin(admin.ModelAdmin):
    list_display = ["referrer", "referred_user", "reward_granted", "created_at"]

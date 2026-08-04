from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "marketing_api"

router = DefaultRouter()
router.register("banners", api_views.BannerViewSet, basename="banner")
router.register("featured-products", api_views.FeaturedProductViewSet, basename="featured-product")
router.register("flash-sales", api_views.FlashSaleViewSet, basename="flash-sale")
router.register("flash-sale-items", api_views.FlashSaleItemViewSet, basename="flash-sale-item")

urlpatterns = [
    path("newsletter/subscribe/", api_views.NewsletterSubscribeView.as_view(), name="newsletter-subscribe"),
    path(
        "newsletter/unsubscribe/",
        api_views.NewsletterUnsubscribeView.as_view(),
        name="newsletter-unsubscribe",
    ),
    path("referral/my-code/", api_views.MyReferralCodeView.as_view(), name="referral-my-code"),
    path("referral/apply/", api_views.ApplyReferralCodeView.as_view(), name="referral-apply"),
] + router.urls

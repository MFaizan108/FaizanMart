from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "coupons_api"

router = DefaultRouter()
router.register("coupons", api_views.CouponViewSet, basename="coupon")

urlpatterns = [
    path("validate/", api_views.ValidateCouponView.as_view(), name="validate"),
] + router.urls

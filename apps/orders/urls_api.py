from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "orders_api"

router = DefaultRouter()
router.register("orders", api_views.OrderViewSet, basename="order")
router.register("returns", api_views.ReturnRequestViewSet, basename="return-request")

urlpatterns = [
    path("checkout/", api_views.CheckoutView.as_view(), name="checkout"),
] + router.urls

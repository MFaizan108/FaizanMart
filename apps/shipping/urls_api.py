from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "shipping_api"

router = DefaultRouter()
router.register("couriers", api_views.CourierViewSet, basename="courier")
router.register("shipments", api_views.ShipmentViewSet, basename="shipment")
router.register("shipping-rules", api_views.ShippingRuleViewSet, basename="shipping-rule")
router.register("deliveries", api_views.DeliveryAssignmentViewSet, basename="delivery")

urlpatterns = [
    path("quote/", api_views.ShippingQuoteView.as_view(), name="quote"),
    path("my-deliveries/", api_views.MyDeliveriesView.as_view(), name="my-deliveries"),
] + router.urls

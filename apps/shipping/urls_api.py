from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "shipping_api"

router = DefaultRouter()
router.register("couriers", api_views.CourierViewSet, basename="courier")
router.register("shipments", api_views.ShipmentViewSet, basename="shipment")

urlpatterns = router.urls

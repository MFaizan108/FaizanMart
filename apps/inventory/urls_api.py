from django.urls import path
from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "inventory_api"

router = DefaultRouter()
router.register("warehouses", api_views.WarehouseViewSet, basename="warehouse")
router.register("stock", api_views.StockViewSet, basename="stock")
router.register("transfers", api_views.TransferViewSet, basename="transfer")
router.register("logs", api_views.InventoryLogViewSet, basename="log")

urlpatterns = [
    path("alerts/low-stock/", api_views.LowStockAlertView.as_view(), name="alert-low-stock"),
    path("alerts/out-of-stock/", api_views.OutOfStockAlertView.as_view(), name="alert-out-of-stock"),
    path(
        "products/<int:product_id>/distribution/",
        api_views.ProductStockDistributionView.as_view(),
        name="product-distribution",
    ),
    path("warehouses/<int:pk>/report/", api_views.WarehouseReportView.as_view(), name="warehouse-report"),
] + router.urls

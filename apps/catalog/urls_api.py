from rest_framework.routers import DefaultRouter

from . import api_views

app_name = "catalog_api"

router = DefaultRouter()
router.register("categories", api_views.CategoryViewSet, basename="category")
router.register("brands", api_views.BrandViewSet, basename="brand")
router.register("tags", api_views.TagViewSet, basename="tag")
router.register("products", api_views.ProductViewSet, basename="product")
router.register("product-images", api_views.ProductImageViewSet, basename="product-image")
router.register("product-variants", api_views.ProductVariantViewSet, basename="product-variant")
router.register(
    "product-specifications",
    api_views.ProductSpecificationViewSet,
    basename="product-specification",
)

urlpatterns = router.urls

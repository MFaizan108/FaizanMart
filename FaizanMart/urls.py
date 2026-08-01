"""
URL configuration for FaizanMart project.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/", include("apps.accounts.urls_api")),
    path("accounts/", include("apps.accounts.urls")),
    path("api/vendors/", include("apps.vendors.urls_api")),
    path("api/catalog/", include("apps.catalog.urls_api")),
    path("api/inventory/", include("apps.inventory.urls_api")),
    path("api/cart/", include("apps.cart.urls_api")),
    path("api/orders/", include("apps.orders.urls_api")),
    path("api/notifications/", include("apps.notifications.urls_api")),
    path("api/payments/", include("apps.payments.urls_api")),
    path("api/coupons/", include("apps.coupons.urls_api")),
    path("api/reviews/", include("apps.reviews.urls_api")),
    path("api/shipping/", include("apps.shipping.urls_api")),
    path("api/support/", include("apps.support.urls_api")),
]

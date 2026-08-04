"""
URL configuration for FaizanMart project.
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .sitemaps import CategorySitemap, ProductSitemap

SITEMAPS = {"products": ProductSitemap, "categories": CategorySitemap}


def robots_txt(request):
    return HttpResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /api/\nSitemap: /sitemap.xml\n",
        content_type="text/plain",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("api/", include("apps.core.urls_api")),
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
    path("api/analytics/", include("apps.analytics.urls_api")),
    path("api/settings/", include("apps.sitesettings.urls_api")),
    path("api/marketing/", include("apps.marketing.urls_api")),
    path("api/chat/", include("apps.chat.urls_api")),
    path("api/assistant/", include("apps.assistant.urls_api")),
]

from django.urls import path

from . import api_views

app_name = "analytics_api"

urlpatterns = [
    path(
        "recommendations/related/<int:product_id>/",
        api_views.RelatedProductsView.as_view(),
        name="related",
    ),
    path(
        "recommendations/frequently-bought-together/<int:product_id>/",
        api_views.FrequentlyBoughtTogetherView.as_view(),
        name="frequently-bought-together",
    ),
    path("recommendations/trending/", api_views.TrendingProductsView.as_view(), name="trending"),
    path("recommendations/best-sellers/", api_views.BestSellersView.as_view(), name="best-sellers"),
    path("recommendations/recently-viewed/", api_views.RecentlyViewedView.as_view(), name="recently-viewed"),
    path("recommendations/track-view/", api_views.TrackViewView.as_view(), name="track-view"),
    path(
        "recommendations/also-viewed/<int:product_id>/",
        api_views.AlsoViewedView.as_view(),
        name="also-viewed",
    ),
    path(
        "recommendations/for-you/",
        api_views.PersonalizedRecommendationsView.as_view(),
        name="for-you",
    ),
    path("vendor/dashboard/", api_views.VendorDashboardView.as_view(), name="vendor-dashboard"),
    path("admin/dashboard/", api_views.AdminDashboardView.as_view(), name="admin-dashboard"),
    path("reports/sales/", api_views.SalesReportView.as_view(), name="report-sales"),
    path("reports/inventory/", api_views.InventoryReportView.as_view(), name="report-inventory"),
    path("reports/vendors/", api_views.VendorReportView.as_view(), name="report-vendors"),
    path("reports/products/", api_views.ProductReportView.as_view(), name="report-products"),
    path("reports/tax/", api_views.TaxReportView.as_view(), name="report-tax"),
    path("reports/refunds/", api_views.RefundReportView.as_view(), name="report-refunds"),
]

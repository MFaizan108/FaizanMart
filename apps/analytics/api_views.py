from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.core.permissions import IsAccountant, IsSuperAdmin, IsVendor, IsWarehouseManager

from . import services
from .serializers import ProductMiniSerializer, TrackViewSerializer

CAN_SEE_INVENTORY_REPORTS = IsWarehouseManager | IsSuperAdmin
CAN_SEE_FINANCE_REPORTS = IsAccountant | IsSuperAdmin

# Trending/best-sellers are derived aggregate stats — cheap to let go stale for a few
# minutes rather than invalidate on every OrderItem write, so this is TTL-only, no signals.
HOMEPAGE_CACHE_TTL = 60 * 10


class RelatedProductsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        return Response(ProductMiniSerializer(services.get_related_products(product), many=True).data)


class FrequentlyBoughtTogetherView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        return Response(
            ProductMiniSerializer(services.get_frequently_bought_together(product), many=True).data
        )


class TrendingProductsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        cache_key = f"analytics:trending:{days}"
        data = cache.get(cache_key)
        if data is None:
            data = ProductMiniSerializer(services.get_trending_products(days=days), many=True).data
            cache.set(cache_key, data, HOMEPAGE_CACHE_TTL)
        return Response(data)


class BestSellersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        days = request.query_params.get("days")
        cache_key = f"analytics:best_sellers:{days or 'all'}"
        data = cache.get(cache_key)
        if data is None:
            data = ProductMiniSerializer(
                services.get_best_sellers(days=int(days) if days else None), many=True
            ).data
            cache.set(cache_key, data, HOMEPAGE_CACHE_TTL)
        return Response(data)


class RecentlyViewedView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(ProductMiniSerializer(services.get_recently_viewed(request.user), many=True).data)


class AlsoViewedView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, product_id):
        product = get_object_or_404(Product, pk=product_id)
        return Response(ProductMiniSerializer(services.get_also_viewed(product), many=True).data)


class PersonalizedRecommendationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            ProductMiniSerializer(services.get_personalized_recommendations(request.user), many=True).data
        )


class TrackViewView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TrackViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = get_object_or_404(Product, pk=serializer.validated_data["product"])
        user = request.user if request.user.is_authenticated else None
        services.record_view(product, user=user)
        return Response(status=204)


class VendorDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self, request):
        return Response(services.vendor_analytics(request.user.store))


class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        return Response(services.admin_analytics())


class SalesReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "super_admin":
            store = None
        elif hasattr(user, "store"):
            store = user.store
        else:
            raise PermissionDenied("Only vendors and admins can view sales reports.")
        return Response(services.sales_report(store=store))


class InventoryReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_SEE_INVENTORY_REPORTS]

    def get(self, request):
        return Response(services.inventory_report())


class VendorReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        return Response(services.vendor_report())


class ProductReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "super_admin":
            store = None
        elif hasattr(user, "store"):
            store = user.store
        else:
            raise PermissionDenied("Only vendors and admins can view product reports.")
        return Response(services.product_report(store=store))


class TaxReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_SEE_FINANCE_REPORTS]

    def get(self, request):
        return Response(services.tax_report())


class RefundReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, CAN_SEE_FINANCE_REPORTS]

    def get(self, request):
        return Response(services.refund_report())

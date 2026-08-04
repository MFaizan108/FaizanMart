from rest_framework import permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsSuperAdminOrReadOnly

from . import services
from .models import Banner, FeaturedProduct, FlashSale, FlashSaleItem
from .serializers import (
    ApplyReferralCodeSerializer,
    BannerSerializer,
    FeaturedProductSerializer,
    FlashSaleItemSerializer,
    FlashSaleSerializer,
    NewsletterEmailSerializer,
    ReferralCodeSerializer,
)


def _is_staff(user):
    return user.is_authenticated and user.role == "super_admin"


class BannerViewSet(viewsets.ModelViewSet):
    serializer_class = BannerSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        if _is_staff(self.request.user):
            return Banner.objects.all()
        position = self.request.query_params.get("position")
        return services.get_active_banners(position=position)


class FeaturedProductViewSet(viewsets.ModelViewSet):
    queryset = FeaturedProduct.objects.select_related("product")
    serializer_class = FeaturedProductSerializer
    permission_classes = [IsSuperAdminOrReadOnly]


class FlashSaleViewSet(viewsets.ModelViewSet):
    serializer_class = FlashSaleSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = FlashSale.objects.prefetch_related("items")
        if not _is_staff(self.request.user) and self.request.query_params.get("live") == "true":
            return services.get_live_flash_sales()
        return queryset


class FlashSaleItemViewSet(viewsets.ModelViewSet):
    queryset = FlashSaleItem.objects.select_related("product", "flash_sale")
    serializer_class = FlashSaleItemSerializer
    permission_classes = [IsSuperAdminOrReadOnly]


class NewsletterSubscribeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = NewsletterEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.subscribe_newsletter(serializer.validated_data["email"])
        return Response({"detail": "Subscribed."})


class NewsletterUnsubscribeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = NewsletterEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.unsubscribe_newsletter(serializer.validated_data["email"])
        return Response({"detail": "Unsubscribed."})


class MyReferralCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = services.get_or_create_referral_code(request.user)
        return Response(ReferralCodeSerializer(code).data)


class ApplyReferralCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ApplyReferralCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.apply_referral_code(serializer.validated_data["code"], request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"detail": "Referral applied. Bonus credited to your wallet."})

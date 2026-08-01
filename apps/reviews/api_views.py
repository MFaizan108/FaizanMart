from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Review, WishlistItem
from .permissions import IsReviewOwnerOrReadOnly
from .serializers import (
    ReviewSerializer,
    ToggleWishlistSerializer,
    VendorReplySerializer,
    WishlistItemSerializer,
)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsReviewOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.select_related("customer", "product").prefetch_related("images")
        product_id = self.request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def perform_create(self, serializer):
        try:
            review = services.create_review(
                customer=self.request.user,
                product=serializer.validated_data["product"],
                rating=serializer.validated_data["rating"],
                title=serializer.validated_data.get("title", ""),
                comment=serializer.validated_data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
        serializer.instance = review

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        # Not self.get_object(): that applies IsReviewOwnerOrReadOnly's object check, which is
        # about the *customer* owning the review, not the *vendor* owning the product. Ownership
        # for a reply is validated by services.add_vendor_reply instead.
        review = get_object_or_404(Review, pk=pk)
        serializer = VendorReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.add_vendor_reply(review, request.user, serializer.validated_data["reply"])
        except ValueError as exc:
            raise PermissionDenied(str(exc))
        return Response(ReviewSerializer(review).data)


class WishlistListView(generics.ListAPIView):
    serializer_class = WishlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WishlistItem.objects.filter(customer=self.request.user).select_related("product")


class ToggleWishlistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ToggleWishlistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.catalog.models import Product

        try:
            product = Product.objects.get(pk=serializer.validated_data["product"])
        except Product.DoesNotExist:
            return Response({"detail": "Product not found."}, status=404)

        added = services.toggle_wishlist(request.user, product)
        return Response({"added": added})

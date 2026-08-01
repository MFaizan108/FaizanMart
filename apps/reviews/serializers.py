from rest_framework import serializers

from .models import Review, ReviewImage, WishlistItem


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "review", "image"]


class ReviewSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    images = ReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "customer_email",
            "rating",
            "title",
            "comment",
            "is_verified_purchase",
            "vendor_reply",
            "vendor_replied_at",
            "images",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "customer_email",
            "is_verified_purchase",
            "vendor_reply",
            "vendor_replied_at",
            "images",
            "created_at",
        ]


class VendorReplySerializer(serializers.Serializer):
    reply = serializers.CharField()


class WishlistItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ["id", "product", "product_name", "product_slug", "product_price", "created_at"]
        read_only_fields = ["id", "product_name", "product_slug", "product_price", "created_at"]


class ToggleWishlistSerializer(serializers.Serializer):
    product = serializers.IntegerField()

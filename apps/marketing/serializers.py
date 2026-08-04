from rest_framework import serializers

from .models import Banner, FeaturedProduct, FlashSale, FlashSaleItem, ReferralCode


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "image",
            "link_url",
            "position",
            "sort_order",
            "is_active",
            "start_date",
            "end_date",
        ]
        read_only_fields = ["id"]


class FeaturedProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.DecimalField(
        source="product.price", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = FeaturedProduct
        fields = ["id", "product", "product_name", "product_price", "sort_order", "featured_at"]
        read_only_fields = ["id", "product_name", "product_price", "featured_at"]


class FlashSaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = FlashSaleItem
        fields = [
            "id",
            "flash_sale",
            "product",
            "product_name",
            "discount_percentage",
            "stock_limit",
            "units_sold",
            "sale_price",
        ]
        read_only_fields = ["id", "product_name", "units_sold", "sale_price"]


class FlashSaleSerializer(serializers.ModelSerializer):
    items = FlashSaleItemSerializer(many=True, read_only=True)
    is_live = serializers.BooleanField(read_only=True)

    class Meta:
        model = FlashSale
        fields = ["id", "name", "starts_at", "ends_at", "is_active", "is_live", "items"]
        read_only_fields = ["id", "is_live", "items"]


class NewsletterEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ReferralCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCode
        fields = ["code", "created_at"]
        read_only_fields = fields


class ApplyReferralCodeSerializer(serializers.Serializer):
    code = serializers.CharField()

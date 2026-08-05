from rest_framework import serializers

from apps.catalog.models import Product, ProductVariant

from .models import CartItem


class ProductMiniSerializer(serializers.ModelSerializer):
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "price", "product_type", "store_id", "store_name", "image_url"]

    def get_image_url(self, product):
        image = next((img for img in product.images.all() if img.is_primary), None) or next(
            iter(product.images.all()), None
        )
        return image.image.url if image else None


class VariantMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "color", "size", "price_override"]


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductMiniSerializer(read_only=True)
    variant = VariantMiniSerializer(read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "variant", "quantity", "unit_price", "line_total", "added_at"]


class AddCartItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(status="published"))
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(), required=False, allow_null=True, default=None
    )
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        variant = attrs.get("variant")
        if variant and variant.product_id != attrs["product"].id:
            raise serializers.ValidationError("This variant does not belong to the given product.")
        return attrs


class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class CartSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    guest_token = serializers.UUIDField(allow_null=True)
    items = CartItemSerializer(many=True)
    items_count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

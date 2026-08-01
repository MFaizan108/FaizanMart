from rest_framework import serializers

from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant, Tag


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "description",
            "image",
            "is_featured",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "slug"]


class ProductOwnedChildSerializer(serializers.ModelSerializer):
    """Shared guard: the `product` a client passes must belong to their own store."""

    def validate_product(self, product):
        request = self.context.get("request")
        if request and product.store.owner_id != request.user.id:
            raise serializers.ValidationError("You do not own this product.")
        return product


class ProductImageSerializer(ProductOwnedChildSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "alt_text", "is_primary", "sort_order"]


class ProductVariantSerializer(ProductOwnedChildSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "product", "sku", "color", "size", "price_override", "image", "is_active"]


class ProductSpecificationSerializer(ProductOwnedChildSerializer):
    class Meta:
        model = ProductSpecification
        fields = ["id", "product", "key", "value", "sort_order"]


class ProductReadSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_slug = serializers.CharField(source="store.slug", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "store",
            "store_name",
            "store_slug",
            "category",
            "brand",
            "tags",
            "name",
            "slug",
            "description",
            "product_type",
            "sku",
            "barcode",
            "price",
            "compare_at_price",
            "weight",
            "warranty_info",
            "digital_file",
            "video_url",
            "meta_title",
            "meta_description",
            "status",
            "images",
            "variants",
            "specifications",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProductWriteSerializer(serializers.ModelSerializer):
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)

    class Meta:
        model = Product
        fields = [
            "category",
            "brand",
            "tags",
            "name",
            "description",
            "product_type",
            "sku",
            "barcode",
            "price",
            "compare_at_price",
            "weight",
            "warranty_info",
            "digital_file",
            "video_url",
            "meta_title",
            "meta_description",
            "status",
        ]

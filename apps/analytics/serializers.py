from rest_framework import serializers

from apps.catalog.models import Product


class ProductMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "slug", "price", "product_type"]


class TrackViewSerializer(serializers.Serializer):
    product = serializers.IntegerField()

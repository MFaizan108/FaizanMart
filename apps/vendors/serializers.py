from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from . import services
from .models import Store

User = get_user_model()


class VendorRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    store_name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        request = self.context["request"]
        user, store = services.register_vendor(**validated_data, request=request)
        return store


class StoreSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Store
        fields = [
            "id",
            "owner_email",
            "name",
            "slug",
            "description",
            "logo",
            "banner",
            "business_name",
            "business_type",
            "business_registration_number",
            "tax_number",
            "bank_name",
            "bank_account_title",
            "bank_account_number",
            "bank_iban",
            "return_policy",
            "shipping_policy",
            "terms_and_conditions",
            "status",
            "rejection_reason",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_email",
            "slug",
            "status",
            "rejection_reason",
            "approved_at",
            "created_at",
            "updated_at",
        ]


class PublicStoreSerializer(serializers.ModelSerializer):
    """Safe-to-expose subset of Store for the public seller storefront page —
    excludes owner contact info, bank/tax details, and internal review fields."""

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "logo",
            "banner",
            "return_policy",
            "shipping_policy",
            "created_at",
        ]
        read_only_fields = fields


class StoreAdminListSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Store
        fields = [
            "id",
            "owner_email",
            "name",
            "slug",
            "business_name",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class StoreRejectSerializer(serializers.Serializer):
    reason = serializers.CharField()

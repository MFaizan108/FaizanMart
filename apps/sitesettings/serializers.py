from rest_framework import serializers

from .models import EmailTemplate, SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name",
            "support_email",
            "support_phone",
            "currency_code",
            "currency_symbol",
            "default_tax_rate",
            "free_shipping_threshold",
            "maintenance_mode",
            "cod_enabled",
            "stripe_enabled",
            "jazzcash_enabled",
            "easypaisa_enabled",
            "wallet_payments_enabled",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = ["id", "key", "subject", "body", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

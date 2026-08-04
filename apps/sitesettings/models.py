from django.db import models

from apps.core.models import TimeStampedModel


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default="FaizanMart")
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=30, blank=True)

    currency_code = models.CharField(max_length=3, default="PKR")
    currency_symbol = models.CharField(max_length=5, default="Rs")
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Percentage, e.g. 5.00 for 5%."
    )
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    maintenance_mode = models.BooleanField(default=False)

    cod_enabled = models.BooleanField(default=True)
    stripe_enabled = models.BooleanField(default=False)
    jazzcash_enabled = models.BooleanField(default=False)
    easypaisa_enabled = models.BooleanField(default=False)
    wallet_payments_enabled = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EmailTemplate(TimeStampedModel):
    key = models.SlugField(max_length=100, unique=True, help_text="e.g. 'order_placed', 'welcome_email'.")
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Use {{ variable }} placeholders.")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.key

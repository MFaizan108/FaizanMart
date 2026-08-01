from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Coupon(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"
        FREE_SHIPPING = "free_shipping", "Free Shipping"

    code = models.CharField(max_length=32, unique=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    store = models.ForeignKey(
        "vendors.Store",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coupons",
        help_text="Blank = platform-wide coupon; set = only valid for this vendor's products.",
    )
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Blank = unlimited.")
    used_count = models.PositiveIntegerField(default=0)
    per_customer_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Blank = unlimited.")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption"
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coupon_redemptions")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} on {self.order.order_number}"

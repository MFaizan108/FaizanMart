from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Banner(TimeStampedModel):
    class Position(models.TextChoices):
        HOME_HERO = "home_hero", "Home Hero"
        HOME_SECONDARY = "home_secondary", "Home Secondary"
        CATEGORY_PAGE = "category_page", "Category Page"

    title = models.CharField(max_length=150)
    image = models.ImageField(upload_to="marketing/banners/")
    link_url = models.CharField(max_length=255, blank=True)
    position = models.CharField(max_length=20, choices=Position.choices, default=Position.HOME_HERO)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_currently_active(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True


class FeaturedProduct(models.Model):
    product = models.OneToOneField(
        "catalog.Product", on_delete=models.CASCADE, related_name="featured_entry"
    )
    sort_order = models.PositiveIntegerField(default=0)
    featured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "-featured_at"]

    def __str__(self):
        return f"Featured: {self.product.name}"


class FlashSale(TimeStampedModel):
    name = models.CharField(max_length=150)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at


class FlashSaleItem(models.Model):
    flash_sale = models.ForeignKey(FlashSale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="flash_sale_items")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    stock_limit = models.PositiveIntegerField(null=True, blank=True)
    units_sold = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("flash_sale", "product")

    def __str__(self):
        return f"{self.product.name} @ {self.discount_percentage}% off in {self.flash_sale.name}"

    @property
    def sale_price(self):
        return (self.product.price * (100 - self.discount_percentage) / 100).quantize(self.product.price)


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email


class ReferralCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=16, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class ReferralSignup(models.Model):
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals_made"
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referred_by_signup"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reward_granted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.referrer.email} referred {self.referred_user.email}"

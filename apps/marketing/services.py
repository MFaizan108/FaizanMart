import uuid
from decimal import Decimal

from django.utils import timezone

from apps.payments import services as payment_services

from .models import Banner, FeaturedProduct, FlashSale, NewsletterSubscriber, ReferralCode, ReferralSignup

REFERRER_BONUS = Decimal("50.00")
REFERRED_USER_BONUS = Decimal("25.00")


def get_active_banners(position=None):
    now = timezone.now()
    queryset = Banner.objects.filter(is_active=True).exclude(end_date__lt=now).exclude(start_date__gt=now)
    if position:
        queryset = queryset.filter(position=position)
    return queryset


def get_featured_products(limit=10):
    return FeaturedProduct.objects.select_related("product")[:limit]


def get_live_flash_sales():
    now = timezone.now()
    return FlashSale.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)


def subscribe_newsletter(email):
    subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email)
    if not created and not subscriber.is_active:
        subscriber.is_active = True
        subscriber.unsubscribed_at = None
        subscriber.save(update_fields=["is_active", "unsubscribed_at"])
    return subscriber


def unsubscribe_newsletter(email):
    subscriber = NewsletterSubscriber.objects.filter(email=email).first()
    if subscriber and subscriber.is_active:
        subscriber.is_active = False
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["is_active", "unsubscribed_at"])
    return subscriber


def get_or_create_referral_code(user):
    referral_code = ReferralCode.objects.filter(user=user).first()
    if referral_code:
        return referral_code
    code = uuid.uuid4().hex[:8].upper()
    while ReferralCode.objects.filter(code=code).exists():
        code = uuid.uuid4().hex[:8].upper()
    return ReferralCode.objects.create(user=user, code=code)


def apply_referral_code(code, referred_user):
    try:
        referral_code = ReferralCode.objects.select_related("user").get(code=code.upper())
    except ReferralCode.DoesNotExist:
        raise ValueError("Invalid referral code.")

    if referral_code.user_id == referred_user.id:
        raise ValueError("You cannot refer yourself.")
    if ReferralSignup.objects.filter(referred_user=referred_user).exists():
        raise ValueError("You have already used a referral code.")

    signup = ReferralSignup.objects.create(referrer=referral_code.user, referred_user=referred_user)
    payment_services.credit_wallet(referral_code.user, REFERRER_BONUS, reason="Referral bonus")
    payment_services.credit_wallet(referred_user, REFERRED_USER_BONUS, reason="Welcome referral bonus")
    signup.reward_granted = True
    signup.save(update_fields=["reward_granted"])
    return signup

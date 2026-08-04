from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from .models import Coupon, CouponRedemption


def get_active_coupon(code):
    coupon = Coupon.objects.filter(code=code.upper(), is_active=True).first()
    if coupon is None:
        raise ValueError("Coupon not found or inactive.")
    now = timezone.now()
    if not (coupon.valid_from <= now <= coupon.valid_until):
        raise ValueError("Coupon is not valid at this time.")
    return coupon


def check_usage_eligibility(coupon, user, subtotal):
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValueError("Coupon usage limit reached.")
    if coupon.per_customer_limit is not None:
        used_by_customer = CouponRedemption.objects.filter(coupon=coupon, customer=user).count()
        if used_by_customer >= coupon.per_customer_limit:
            raise ValueError("You have already used this coupon the maximum number of times.")
    if subtotal < coupon.min_order_amount:
        raise ValueError(f"Order must be at least {coupon.min_order_amount} to use this coupon.")


def validate_coupon(code, user, subtotal, *, lock=False):
    coupon = get_active_coupon(code)
    if lock:
        coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
    check_usage_eligibility(coupon, user, subtotal)
    return coupon


def compute_discount(coupon, subtotal, shipping_cost=Decimal("0")):
    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        return (subtotal * coupon.value / Decimal("100")).quantize(Decimal("0.01"))
    if coupon.discount_type == Coupon.DiscountType.FIXED:
        return min(coupon.value, subtotal)
    if coupon.discount_type == Coupon.DiscountType.FREE_SHIPPING:
        return shipping_cost
    return Decimal("0")


def redeem_coupon(coupon, order, customer, discount_amount):
    CouponRedemption.objects.create(
        coupon=coupon, order=order, customer=customer, discount_amount=discount_amount
    )
    Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)

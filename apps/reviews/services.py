from django.utils import timezone

from apps.orders.models import Order, OrderItem

from .models import Review, WishlistItem

PURCHASED_STATUSES = [Order.Status.SHIPPED, Order.Status.DELIVERED]


def is_verified_purchase(customer, product):
    return OrderItem.objects.filter(
        order__customer=customer, product=product, order__status__in=PURCHASED_STATUSES
    ).exists()


def create_review(*, customer, product, rating, title="", comment=""):
    if Review.objects.filter(product=product, customer=customer).exists():
        raise ValueError("You have already reviewed this product.")
    return Review.objects.create(
        product=product,
        customer=customer,
        rating=rating,
        title=title,
        comment=comment,
        is_verified_purchase=is_verified_purchase(customer, product),
    )


def add_vendor_reply(review, vendor_user, reply_text):
    if review.product.store.owner_id != vendor_user.id:
        raise ValueError("You can only reply to reviews on your own products.")
    review.vendor_reply = reply_text
    review.vendor_replied_at = timezone.now()
    review.save(update_fields=["vendor_reply", "vendor_replied_at"])
    return review


def toggle_wishlist(customer, product):
    item = WishlistItem.objects.filter(customer=customer, product=product).first()
    if item:
        item.delete()
        return False
    WishlistItem.objects.create(customer=customer, product=product)
    return True

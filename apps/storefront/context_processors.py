import uuid

from apps.cart import services as cart_services
from apps.cart.models import Cart
from apps.catalog.models import Category
from apps.reviews.models import WishlistItem

GUEST_CART_SESSION_KEY = "cart_guest_token"


def cart(request):
    """Cart summary + guest token, available in every template.

    Session-rendered pages need a way to identify an anonymous visitor's cart across
    full-page navigations (there's no client-side token store here) — the guest cart's
    token is kept in the Django session instead, and handed to the page as
    `window.CART_TOKEN` so storefront.js can send it as X-Cart-Token on fetch() calls to
    the same cart API the DRF layer already exposes.
    """
    if request.user.is_authenticated:
        cart_obj, _ = Cart.objects.get_or_create(user=request.user)
    else:
        token = request.session.get(GUEST_CART_SESSION_KEY)
        cart_obj = Cart.objects.filter(guest_token=token).first() if token else None
        if cart_obj is None:
            cart_obj = Cart.objects.create(guest_token=uuid.uuid4())
            request.session[GUEST_CART_SESSION_KEY] = str(cart_obj.guest_token)

    totals = cart_services.cart_totals(cart_obj)
    wishlist_count = (
        WishlistItem.objects.filter(customer=request.user).count() if request.user.is_authenticated else 0
    )
    return {
        "cart_token": str(cart_obj.guest_token) if cart_obj.guest_token else "",
        "cart_items_count": totals["items_count"],
        "cart_subtotal": totals["subtotal"],
        "wishlist_count": wishlist_count,
        "nav_categories": Category.objects.filter(is_active=True, parent__isnull=True)[:12],
    }

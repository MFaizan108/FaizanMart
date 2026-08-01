import uuid
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.catalog.models import Product
from apps.inventory.models import Stock

from .models import Cart, CartItem

CART_TOKEN_HEADER = "X-Cart-Token"


def resolve_cart(request):
    """Returns (cart, is_new_guest_cart)."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, False

    token_header = request.headers.get(CART_TOKEN_HEADER)
    if token_header:
        try:
            token = uuid.UUID(token_header)
        except ValueError:
            token = None
        if token:
            cart = Cart.objects.filter(guest_token=token).first()
            if cart:
                return cart, False

    cart = Cart.objects.create(guest_token=uuid.uuid4())
    return cart, True


def _available_stock(product):
    """None means untracked/unlimited (digital product, or no Stock rows yet)."""
    if product.product_type == Product.ProductType.DIGITAL:
        return None
    stocks = Stock.objects.filter(product=product)
    if not stocks.exists():
        return None
    agg = stocks.aggregate(total=Sum("quantity"), reserved=Sum("reserved_quantity"))
    return (agg["total"] or 0) - (agg["reserved"] or 0)


def add_item(*, cart, product, variant, quantity):
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")

    existing = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
    desired_total = quantity + (existing.quantity if existing else 0)

    available = _available_stock(product)
    if available is not None and desired_total > available:
        raise ValueError(f"Only {available} unit(s) available.")

    if existing:
        existing.quantity = desired_total
        existing.save(update_fields=["quantity"])
        return existing
    return CartItem.objects.create(cart=cart, product=product, variant=variant, quantity=quantity)


def update_item_quantity(item, quantity):
    if quantity < 1:
        raise ValueError("Quantity must be at least 1; remove the item instead.")
    available = _available_stock(item.product)
    if available is not None and quantity > available:
        raise ValueError(f"Only {available} unit(s) available.")
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_item(item):
    item.delete()


def clear_cart(cart):
    cart.items.all().delete()


def merge_guest_cart(user, guest_token):
    try:
        token = uuid.UUID(str(guest_token))
    except (ValueError, TypeError):
        raise ValueError("Invalid guest token.")

    guest_cart = Cart.objects.filter(guest_token=token).first()
    if guest_cart is None:
        raise ValueError("Guest cart not found.")

    user_cart, _ = Cart.objects.get_or_create(user=user)
    with transaction.atomic():
        for item in guest_cart.items.all():
            existing = CartItem.objects.filter(
                cart=user_cart, product=item.product, variant=item.variant
            ).first()
            if existing:
                existing.quantity += item.quantity
                existing.save(update_fields=["quantity"])
            else:
                item.cart = user_cart
                item.save(update_fields=["cart"])
        guest_cart.delete()
    return user_cart


def cart_totals(cart):
    items = list(cart.items.select_related("product", "variant"))
    subtotal = sum((item.line_total for item in items), Decimal("0.00"))
    return {"items_count": sum(item.quantity for item in items), "subtotal": subtotal}

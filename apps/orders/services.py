from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.cart import services as cart_services
from apps.cart.models import Cart
from apps.catalog.models import Product
from apps.coupons import services as coupon_services
from apps.inventory import services as inventory_services
from apps.inventory.models import Stock
from apps.notifications import services as notification_services

from .models import Order, OrderItem, OrderStatusHistory

ALLOWED_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PROCESSING, Order.Status.CANCELLED},
    Order.Status.PROCESSING: {Order.Status.PACKED, Order.Status.CANCELLED},
    Order.Status.PACKED: {Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: {Order.Status.RETURNED},
    Order.Status.RETURNED: {Order.Status.REFUNDED},
    Order.Status.CANCELLED: set(),
    Order.Status.REFUNDED: set(),
}


def _pick_warehouse_with_stock(product, quantity):
    candidates = Stock.objects.filter(product=product).with_available().order_by("-available")
    for stock in candidates:
        if stock.available >= quantity:
            return stock.warehouse
    return None


def place_order(*, user, order_fields):
    order_fields = dict(order_fields)
    coupon_code = order_fields.pop("coupon_code", "")

    cart, _ = Cart.objects.get_or_create(user=user)
    items = list(cart.items.select_related("product", "variant", "product__store"))
    if not items:
        raise ValueError("Your cart is empty.")

    groups = defaultdict(list)
    for item in items:
        groups[item.product.store_id].append(item)

    coupon = None
    if coupon_code:
        cart_subtotal = sum((item.unit_price * item.quantity for item in items), Decimal("0"))
        coupon = coupon_services.validate_coupon(coupon_code, user, cart_subtotal)
        if coupon.store_id is not None and coupon.store_id not in groups:
            raise ValueError(f"Coupon '{coupon_code}' is not valid for the products in your cart.")
    coupon_applied = False

    orders = []
    with transaction.atomic():
        for group_items in groups.values():
            store = group_items[0].product.store
            subtotal = sum((item.unit_price * item.quantity for item in group_items), Decimal("0"))

            discount_amount = Decimal("0")
            group_coupon = None
            if coupon and not coupon_applied and (coupon.store_id is None or coupon.store_id == store.id):
                group_coupon = coupon
                discount_amount = coupon_services.compute_discount(
                    coupon, subtotal, order_fields.get("shipping_cost", Decimal("0"))
                )
                coupon_applied = True

            order = Order.objects.create(
                customer=user, store=store, discount_amount=discount_amount, **order_fields
            )

            for item in group_items:
                unit_price = item.unit_price
                warehouse = None
                if item.product.product_type != Product.ProductType.DIGITAL:
                    warehouse = _pick_warehouse_with_stock(item.product, item.quantity)
                    if warehouse is None:
                        raise ValueError(f"Insufficient stock for '{item.product.name}'.")
                    inventory_services.reserve_stock(
                        product=item.product,
                        warehouse=warehouse,
                        quantity=item.quantity,
                        note=f"Reserved for order {order.order_number}",
                        user=user,
                    )
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    warehouse=warehouse,
                    product_name=item.product.name,
                    sku=item.variant.sku if item.variant else item.product.sku,
                    unit_price=unit_price,
                    quantity=item.quantity,
                )

            order.subtotal = subtotal
            order.total_amount = subtotal - discount_amount + order.tax_amount + order.shipping_cost
            order.save(update_fields=["subtotal", "total_amount"])
            OrderStatusHistory.objects.create(
                order=order, status=Order.Status.PENDING, note="Order placed", changed_by=user
            )

            if group_coupon:
                coupon_services.redeem_coupon(group_coupon, order, user, discount_amount)

            orders.append(order)

        cart_services.clear_cart(cart)

    for order in orders:
        notification_services.notify(
            order.customer,
            title=f"Order {order.order_number} placed",
            message=f"Your order with {order.store.name} has been placed and is pending confirmation.",
            notification_type="order_update",
        )
        notification_services.notify(
            order.store.owner,
            title=f"New order {order.order_number}",
            message=f"You have a new order from {order.customer.email}.",
            notification_type="order_update",
        )

    return orders


def transition_status(order, new_status, user=None, note=""):
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise ValueError(f"Cannot move an order from '{order.status}' to '{new_status}'.")

    with transaction.atomic():
        for item in order.items.select_related("product", "warehouse"):
            if item.warehouse is None or item.product is None:
                continue
            if new_status == Order.Status.SHIPPED:
                inventory_services.adjust_stock(
                    product=item.product,
                    warehouse=item.warehouse,
                    delta=-item.quantity,
                    change_type="sale",
                    note=f"Shipped for order {order.order_number}",
                    user=user,
                )
                inventory_services.release_stock(
                    product=item.product,
                    warehouse=item.warehouse,
                    quantity=item.quantity,
                    note=f"Reservation cleared on shipment of order {order.order_number}",
                    user=user,
                )
            elif new_status == Order.Status.CANCELLED:
                inventory_services.release_stock(
                    product=item.product,
                    warehouse=item.warehouse,
                    quantity=item.quantity,
                    note=f"Order {order.order_number} cancelled",
                    user=user,
                )
            elif new_status == Order.Status.RETURNED:
                inventory_services.adjust_stock(
                    product=item.product,
                    warehouse=item.warehouse,
                    delta=item.quantity,
                    change_type="adjustment",
                    note=f"Return for order {order.order_number}",
                    user=user,
                )

        order.status = new_status
        if new_status == Order.Status.CANCELLED:
            order.cancelled_at = timezone.now()
            order.cancel_reason = note
            order.save(update_fields=["status", "cancelled_at", "cancel_reason"])
        else:
            order.save(update_fields=["status"])

        OrderStatusHistory.objects.create(order=order, status=new_status, note=note, changed_by=user)

    notification_services.notify(
        order.customer,
        title=f"Order {order.order_number} is now {order.get_status_display()}",
        message=note or "",
        notification_type="order_update",
    )

    return order

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task
def send_order_confirmation_email_task(order_id):
    """Emails the customer a plain-text order confirmation/invoice right after checkout.
    Runs off the request thread since it involves an SMTP round-trip."""
    from .models import Order

    try:
        order = Order.objects.select_related("customer", "store").prefetch_related("items").get(pk=order_id)
    except Order.DoesNotExist:
        return

    lines = [
        f"Hi {order.customer.get_short_name()},",
        "",
        f"Thanks for your order with {order.store.name} — here's your receipt.",
        "",
        f"Order: {order.order_number}",
        f"Payment method: {order.get_payment_method_display()}",
        "",
        "Items:",
    ]
    for item in order.items.all():
        lines.append(f"  {item.quantity} x {item.product_name} @ {item.unit_price} = {item.line_total}")
    lines += [
        "",
        f"Subtotal: {order.subtotal}",
        f"Discount: -{order.discount_amount}",
        f"Tax: {order.tax_amount}",
        f"Shipping: {order.shipping_cost}",
        f"Total: {order.total_amount}",
        "",
        f"Shipping to: {order.shipping_full_name}, {order.shipping_address_line}, "
        f"{order.shipping_city}, {order.shipping_country}",
    ]

    send_mail(
        subject=f"Your FaizanMart order {order.order_number}",
        message="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.customer.email],
    )

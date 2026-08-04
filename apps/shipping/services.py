from django.db import transaction
from django.utils import timezone

from apps.notifications import services as notification_services
from apps.orders import services as orders_services
from apps.orders.models import Order

from .models import DeliveryAssignment, Shipment
from .rules import calculate_shipping_cost  # noqa: F401  (re-exported for callers of this module)

ALLOWED_TRANSITIONS = {
    Shipment.Status.LABEL_CREATED: {Shipment.Status.IN_TRANSIT, Shipment.Status.FAILED},
    Shipment.Status.IN_TRANSIT: {Shipment.Status.OUT_FOR_DELIVERY, Shipment.Status.FAILED},
    Shipment.Status.OUT_FOR_DELIVERY: {Shipment.Status.DELIVERED, Shipment.Status.FAILED},
    Shipment.Status.DELIVERED: set(),
    Shipment.Status.FAILED: set(),
}


def create_shipment(order, courier, tracking_number=""):
    if Shipment.objects.filter(order=order).exists():
        raise ValueError("This order already has a shipment.")
    return Shipment.objects.create(order=order, courier=courier, tracking_number=tracking_number)


def update_shipment_status(shipment, new_status):
    allowed = ALLOWED_TRANSITIONS.get(shipment.status, set())
    if new_status not in allowed:
        raise ValueError(f"Cannot move a shipment from '{shipment.status}' to '{new_status}'.")
    shipment.status = new_status
    if new_status == Shipment.Status.IN_TRANSIT and shipment.shipped_at is None:
        shipment.shipped_at = timezone.now()
    if new_status == Shipment.Status.DELIVERED:
        shipment.delivered_at = timezone.now()
    shipment.save(update_fields=["status", "shipped_at", "delivered_at", "updated_at"])
    return shipment


DELIVERY_ALLOWED_TRANSITIONS = {
    DeliveryAssignment.Status.ASSIGNED: {DeliveryAssignment.Status.PICKED_UP, DeliveryAssignment.Status.FAILED},
    DeliveryAssignment.Status.PICKED_UP: {
        DeliveryAssignment.Status.OUT_FOR_DELIVERY, DeliveryAssignment.Status.FAILED
    },
    DeliveryAssignment.Status.OUT_FOR_DELIVERY: {
        DeliveryAssignment.Status.DELIVERED, DeliveryAssignment.Status.FAILED
    },
    DeliveryAssignment.Status.DELIVERED: set(),
    DeliveryAssignment.Status.FAILED: set(),
}


@transaction.atomic
def assign_delivery(order, delivery_boy, assigned_by=None):
    if delivery_boy.role != "delivery_boy":
        raise ValueError(f"{delivery_boy.email} is not a delivery boy.")
    if order.status not in (Order.Status.PACKED, Order.Status.SHIPPED):
        raise ValueError(f"Order must be packed before it can be assigned for delivery (currently '{order.status}').")
    has_active = order.delivery_assignments.exclude(
        status__in=[DeliveryAssignment.Status.FAILED, DeliveryAssignment.Status.DELIVERED]
    ).exists()
    if has_active:
        raise ValueError(f"Order {order.order_number} already has an active delivery assignment.")

    assignment = DeliveryAssignment.objects.create(order=order, delivery_boy=delivery_boy)
    notification_services.notify(
        delivery_boy,
        title=f"New delivery assigned: {order.order_number}",
        message=f"You've been assigned to deliver order {order.order_number}.",
        notification_type="order_update",
    )
    return assignment


@transaction.atomic
def update_delivery_status(assignment, new_status, user=None, failure_reason=""):
    allowed = DELIVERY_ALLOWED_TRANSITIONS.get(assignment.status, set())
    if new_status not in allowed:
        raise ValueError(f"Cannot move a delivery from '{assignment.status}' to '{new_status}'.")

    now = timezone.now()
    order = assignment.order

    if new_status == DeliveryAssignment.Status.PICKED_UP:
        assignment.picked_up_at = now
        if order.status == Order.Status.PACKED:
            orders_services.transition_status(order, Order.Status.SHIPPED, user=user, note="Picked up by delivery boy")
    elif new_status == DeliveryAssignment.Status.OUT_FOR_DELIVERY:
        assignment.out_for_delivery_at = now
    elif new_status == DeliveryAssignment.Status.DELIVERED:
        assignment.delivered_at = now
        if order.status == Order.Status.SHIPPED:
            orders_services.transition_status(
                order, Order.Status.DELIVERED, user=user, note="Delivered by delivery boy"
            )
    elif new_status == DeliveryAssignment.Status.FAILED:
        assignment.failed_at = now
        assignment.failure_reason = failure_reason
        notification_services.notify(
            order.customer,
            title=f"Delivery attempt failed for {order.order_number}",
            message=failure_reason or "The delivery could not be completed. It will be reattempted.",
            notification_type="order_update",
        )

    assignment.status = new_status
    assignment.save()
    return assignment

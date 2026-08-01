from django.utils import timezone

from .models import Shipment

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

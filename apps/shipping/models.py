from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class ShippingRule(TimeStampedModel):
    """A rate rule matched against a checkout's destination/order details. Blank/null on any
    condition field means "matches anything" for that dimension. Rules are evaluated in
    `-priority` order and the first full match wins — e.g. "Lahore -> Rs.150", "Karachi ->
    Rs.250", "Free shipping on orders over Rs.5000" as three separate rules, the free-shipping
    one given a higher priority so it's checked (and can win) before the flat city rates."""

    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher values are evaluated first.")

    country = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    store = models.ForeignKey(
        "vendors.Store", on_delete=models.CASCADE, null=True, blank=True, related_name="shipping_rules"
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.CASCADE, null=True, blank=True, related_name="shipping_rules"
    )
    min_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    max_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_order_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free_shipping = models.BooleanField(default=False)

    class Meta:
        ordering = ["-priority", "id"]

    def __str__(self):
        return self.name


class Courier(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    tracking_url_template = models.CharField(
        max_length=255, blank=True, help_text="Use {tracking_number} as a placeholder."
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Shipment(TimeStampedModel):
    class Status(models.TextChoices):
        LABEL_CREATED = "label_created", "Label Created"
        IN_TRANSIT = "in_transit", "In Transit"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="shipment")
    courier = models.ForeignKey(Courier, on_delete=models.PROTECT, related_name="shipments")
    tracking_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.LABEL_CREATED)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shipment for {self.order.order_number}"

    @property
    def tracking_url(self):
        if self.courier.tracking_url_template and self.tracking_number:
            return self.courier.tracking_url_template.format(tracking_number=self.tracking_number)
        return ""


class DeliveryAssignment(TimeStampedModel):
    """In-house last-mile delivery (as opposed to Shipment, which tracks a third-party
    Courier). Flow: Order reaches PACKED -> assigned to a delivery_boy -> picked_up (which
    also drives the Order into SHIPPED, same trigger point stock is decremented at for
    courier shipments) -> out_for_delivery -> delivered (drives Order into DELIVERED) or
    failed. A FK (not OneToOne) to Order so a failed attempt can be reassigned — a new row is
    created rather than the failed one reused, keeping the full attempt history."""

    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        PICKED_UP = "picked_up", "Picked Up"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed Delivery"

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="delivery_assignments")
    delivery_boy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="delivery_assignments"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    out_for_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.order.order_number} -> {self.delivery_boy.email} ({self.status})"

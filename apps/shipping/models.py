from django.db import models

from apps.core.models import TimeStampedModel


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

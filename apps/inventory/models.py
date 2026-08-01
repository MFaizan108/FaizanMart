from django.conf import settings
from django.db import models
from django.db.models import F

from apps.core.models import TimeStampedModel


class Warehouse(TimeStampedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_warehouses",
        limit_choices_to={"role": "warehouse_manager"},
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class StockQuerySet(models.QuerySet):
    def with_available(self):
        return self.annotate(available=F("quantity") - F("reserved_quantity"))

    def low_stock(self):
        return self.with_available().filter(available__gt=0, available__lte=F("low_stock_threshold"))

    def out_of_stock(self):
        return self.with_available().filter(available__lte=0)


class Stock(TimeStampedModel):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="stock_entries")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stock_entries")
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)

    objects = StockQuerySet.as_manager()

    class Meta:
        unique_together = ("product", "warehouse")
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.code}: {self.quantity}"

    @property
    def available_quantity(self):
        return self.quantity - self.reserved_quantity

    @property
    def is_out_of_stock(self):
        return self.available_quantity <= 0

    @property
    def is_low_stock(self):
        return 0 < self.available_quantity <= self.low_stock_threshold


class StockTransfer(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="transfers")
    from_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="outgoing_transfers"
    )
    to_warehouse = models.ForeignKey(
        Warehouse, on_delete=models.CASCADE, related_name="incoming_transfers"
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="stock_transfers"
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transfer {self.product.name}: {self.from_warehouse.code} -> {self.to_warehouse.code}"


class InventoryLog(models.Model):
    class ChangeType(models.TextChoices):
        RESTOCK = "restock", "Restock"
        SALE = "sale", "Sale"
        ADJUSTMENT = "adjustment", "Adjustment"
        TRANSFER_IN = "transfer_in", "Transfer In"
        TRANSFER_OUT = "transfer_out", "Transfer Out"
        RESERVATION = "reservation", "Reservation"
        RELEASE = "release", "Release"

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="inventory_logs")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="inventory_logs")
    change_type = models.CharField(max_length=20, choices=ChangeType.choices)
    quantity_delta = models.IntegerField(default=0)
    reserved_delta = models.IntegerField(default=0)
    resulting_quantity = models.PositiveIntegerField()
    resulting_reserved_quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="inventory_logs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} @ {self.warehouse.code}: {self.change_type} ({self.quantity_delta:+d})"

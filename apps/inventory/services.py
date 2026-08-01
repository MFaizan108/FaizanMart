from django.db import transaction
from django.utils import timezone

from .models import InventoryLog, Stock, StockTransfer


def adjust_stock(*, product, warehouse, delta, change_type, note="", user=None):
    with transaction.atomic():
        stock, _ = Stock.objects.select_for_update().get_or_create(product=product, warehouse=warehouse)
        new_quantity = stock.quantity + delta
        if new_quantity < 0:
            raise ValueError("Adjustment would make stock negative.")
        stock.quantity = new_quantity
        stock.save(update_fields=["quantity", "updated_at"])
        InventoryLog.objects.create(
            product=product,
            warehouse=warehouse,
            change_type=change_type,
            quantity_delta=delta,
            reserved_delta=0,
            resulting_quantity=stock.quantity,
            resulting_reserved_quantity=stock.reserved_quantity,
            note=note,
            created_by=user,
        )
    return stock


def reserve_stock(*, product, warehouse, quantity, note="", user=None):
    with transaction.atomic():
        try:
            stock = Stock.objects.select_for_update().get(product=product, warehouse=warehouse)
        except Stock.DoesNotExist:
            raise ValueError("No stock exists for this product at this warehouse.")
        if stock.available_quantity < quantity:
            raise ValueError("Not enough available stock to reserve.")
        stock.reserved_quantity += quantity
        stock.save(update_fields=["reserved_quantity", "updated_at"])
        InventoryLog.objects.create(
            product=product,
            warehouse=warehouse,
            change_type=InventoryLog.ChangeType.RESERVATION,
            quantity_delta=0,
            reserved_delta=quantity,
            resulting_quantity=stock.quantity,
            resulting_reserved_quantity=stock.reserved_quantity,
            note=note,
            created_by=user,
        )
    return stock


def release_stock(*, product, warehouse, quantity, note="", user=None):
    with transaction.atomic():
        try:
            stock = Stock.objects.select_for_update().get(product=product, warehouse=warehouse)
        except Stock.DoesNotExist:
            raise ValueError("No stock exists for this product at this warehouse.")
        if stock.reserved_quantity < quantity:
            raise ValueError("Cannot release more than is currently reserved.")
        stock.reserved_quantity -= quantity
        stock.save(update_fields=["reserved_quantity", "updated_at"])
        InventoryLog.objects.create(
            product=product,
            warehouse=warehouse,
            change_type=InventoryLog.ChangeType.RELEASE,
            quantity_delta=0,
            reserved_delta=-quantity,
            resulting_quantity=stock.quantity,
            resulting_reserved_quantity=stock.reserved_quantity,
            note=note,
            created_by=user,
        )
    return stock


def create_transfer(*, product, from_warehouse, to_warehouse, quantity, requested_by):
    if from_warehouse == to_warehouse:
        raise ValueError("Source and destination warehouse must differ.")
    try:
        from_stock = Stock.objects.get(product=product, warehouse=from_warehouse)
    except Stock.DoesNotExist:
        raise ValueError("No stock exists for this product at the source warehouse.")
    if from_stock.available_quantity < quantity:
        raise ValueError("Not enough available stock at the source warehouse.")
    return StockTransfer.objects.create(
        product=product,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        quantity=quantity,
        requested_by=requested_by,
    )


def complete_transfer(transfer, user=None):
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Only pending transfers can be completed.")
    with transaction.atomic():
        adjust_stock(
            product=transfer.product,
            warehouse=transfer.from_warehouse,
            delta=-transfer.quantity,
            change_type=InventoryLog.ChangeType.TRANSFER_OUT,
            note=f"Transfer #{transfer.pk}",
            user=user,
        )
        adjust_stock(
            product=transfer.product,
            warehouse=transfer.to_warehouse,
            delta=transfer.quantity,
            change_type=InventoryLog.ChangeType.TRANSFER_IN,
            note=f"Transfer #{transfer.pk}",
            user=user,
        )
        transfer.status = StockTransfer.Status.COMPLETED
        transfer.completed_at = timezone.now()
        transfer.save(update_fields=["status", "completed_at"])
    return transfer


def cancel_transfer(transfer):
    if transfer.status != StockTransfer.Status.PENDING:
        raise ValueError("Only pending transfers can be cancelled.")
    transfer.status = StockTransfer.Status.CANCELLED
    transfer.save(update_fields=["status"])
    return transfer

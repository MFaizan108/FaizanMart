from apps.inventory.models import Stock, Warehouse
from apps.notifications import services as notification_services

from .models import Product

DEFAULT_WAREHOUSE_CODE = "MAIN"


def get_default_warehouse():
    """Sellers don't manage their own warehouses — everything they stock goes into one
    shared default warehouse, get-or-created on first use. A real multi-warehouse setup
    (per-seller or per-region) is out of scope for this marketplace's current size."""
    warehouse, _ = Warehouse.objects.get_or_create(
        code=DEFAULT_WAREHOUSE_CODE, defaults={"name": "Main Warehouse"}
    )
    return warehouse


def set_stock_quantity(product, quantity):
    if product.product_type == Product.ProductType.DIGITAL:
        return None
    warehouse = get_default_warehouse()
    stock, _ = Stock.objects.update_or_create(
        product=product, warehouse=warehouse, defaults={"quantity": quantity}
    )
    return stock


def notify_admins_product_pending(product):
    notification_services.notify_admins(
        title="New product pending review",
        message=f"'{product.name}' from {product.store.name} is waiting for approval.",
        link="/staff/review/",
    )


def approve_product(product, admin_user):
    product.status = Product.Status.PUBLISHED
    product.rejection_reason = ""
    product.save(update_fields=["status", "rejection_reason"])
    notification_services.notify(
        product.store.owner,
        title="Product approved",
        message=f"'{product.name}' is now live on FaizanMart.",
        notification_type="vendor_approval",
    )
    return product


def reject_product(product, admin_user, reason):
    product.status = Product.Status.REJECTED
    product.rejection_reason = reason
    product.save(update_fields=["status", "rejection_reason"])
    notification_services.notify(
        product.store.owner,
        title="Product rejected",
        message=f"'{product.name}' was rejected: {reason}",
        notification_type="vendor_approval",
    )
    return product

"""Pure ShippingRule matching — kept separate from services.py so orders/services.py can
import just this (no dependency on orders) without creating a circular import with
services.py, which itself needs orders.services for delivery-status-driven order transitions.
"""

from decimal import Decimal

from .models import ShippingRule


def calculate_shipping_cost(
    *, country="", province="", city="", store=None, warehouse=None,
    total_weight=Decimal("0"), order_amount=Decimal("0"),
):
    """Returns the Decimal cost from the highest-priority fully-matching active ShippingRule,
    or None if nothing matches (caller decides the fallback, e.g. a flat default rate)."""
    for rule in ShippingRule.objects.filter(is_active=True):
        if rule.country and rule.country.lower() != (country or "").lower():
            continue
        if rule.province and rule.province.lower() != (province or "").lower():
            continue
        if rule.city and rule.city.lower() != (city or "").lower():
            continue
        if rule.store_id and (store is None or rule.store_id != store.id):
            continue
        if rule.warehouse_id and (warehouse is None or rule.warehouse_id != warehouse.id):
            continue
        if rule.min_weight is not None and total_weight < rule.min_weight:
            continue
        if rule.max_weight is not None and total_weight > rule.max_weight:
            continue
        if rule.min_order_amount is not None and order_amount < rule.min_order_amount:
            continue
        if rule.max_order_amount is not None and order_amount > rule.max_order_amount:
            continue
        return Decimal("0") if rule.is_free_shipping else rule.shipping_cost
    return None

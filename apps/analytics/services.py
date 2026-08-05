from datetime import timedelta

from dateutil.relativedelta import relativedelta

from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.catalog.models import Product
from apps.inventory.models import Stock
from apps.orders.models import Order, OrderItem
from apps.payments.models import PaymentTransaction
from apps.vendors.models import Store

from .models import ProductView

PURCHASABLE_STATUSES = [Order.Status.SHIPPED, Order.Status.DELIVERED]


def record_view(product, user=None):
    return ProductView.objects.create(product=product, user=user)


def get_recently_viewed(user, limit=10):
    # Bounded to a small recent window (not every ProductView the user has ever generated) —
    # a plain `.distinct()` on `values_list("product_id")` can't also `.order_by("-viewed_at")`
    # in Postgres (DISTINCT requires ORDER BY columns in the select list), so this dedupes the
    # most recent slice in Python instead of scanning the user's entire view history.
    recent_ids = ProductView.objects.filter(user=user).order_by("-viewed_at").values_list(
        "product_id", flat=True
    )[: limit * 10]
    seen_product_ids = []
    for product_id in recent_ids:
        if product_id not in seen_product_ids:
            seen_product_ids.append(product_id)
        if len(seen_product_ids) >= limit:
            break
    products = Product.objects.filter(pk__in=seen_product_ids, status=Product.Status.PUBLISHED)
    products_by_id = {p.id: p for p in products}
    return [products_by_id[pid] for pid in seen_product_ids if pid in products_by_id]


def get_related_products(product, limit=8):
    return Product.objects.filter(
        category=product.category, status=Product.Status.PUBLISHED
    ).exclude(pk=product.pk)[:limit]


def get_frequently_bought_together(product, limit=8):
    order_ids = OrderItem.objects.filter(product=product).values_list("order_id", flat=True)
    companion_ids = (
        OrderItem.objects.filter(order_id__in=order_ids)
        .exclude(product=product)
        .values("product_id")
        .annotate(times_bought_together=Count("id"))
        .order_by("-times_bought_together")[:limit]
    )
    ids_in_order = [row["product_id"] for row in companion_ids]
    products_by_id = Product.objects.in_bulk(ids_in_order)
    return [products_by_id[pid] for pid in ids_in_order if pid in products_by_id]


def get_also_viewed(product, limit=8):
    """Item-item collaborative filtering from view history: products viewed by the same
    people who viewed this one — the view-based counterpart to "frequently bought together"."""
    viewer_ids = (
        ProductView.objects.filter(product=product).exclude(user=None).values_list("user_id", flat=True).distinct()
    )
    companion_ids = (
        ProductView.objects.filter(user_id__in=viewer_ids)
        .exclude(product=product)
        .values("product_id")
        .annotate(co_view_count=Count("user_id", distinct=True))
        .order_by("-co_view_count")[:limit]
    )
    ids_in_order = [row["product_id"] for row in companion_ids]
    products_by_id = Product.objects.filter(pk__in=ids_in_order, status=Product.Status.PUBLISHED).in_bulk()
    return [products_by_id[pid] for pid in ids_in_order if pid in products_by_id]


def get_personalized_recommendations(user, limit=10):
    """Hybrid recommender for a logged-in user: user-based collaborative filtering (products
    liked by users with overlapping view history) layered with content-based matching (same
    categories the user already engaged with), falling back to best-sellers/trending for
    cold-start users with no history yet, or to fill out a short list."""
    viewed_ids = set(ProductView.objects.filter(user=user).values_list("product_id", flat=True))
    purchased_ids = set(
        OrderItem.objects.filter(order__customer=user, order__status__in=PURCHASABLE_STATUSES).values_list(
            "product_id", flat=True
        )
    )
    interacted_ids = viewed_ids | purchased_ids

    if not interacted_ids:
        fallback = get_best_sellers(limit=limit)
        return fallback if fallback else list(get_trending_products(limit=limit))

    similar_user_ids = (
        ProductView.objects.filter(product_id__in=interacted_ids)
        .exclude(user=user)
        .exclude(user=None)
        .values("user_id")
        .annotate(overlap=Count("product_id", distinct=True))
        .order_by("-overlap")
        .values_list("user_id", flat=True)[:50]
    )
    collaborative_ids = list(
        ProductView.objects.filter(user_id__in=similar_user_ids)
        .exclude(product_id__in=interacted_ids)
        .values("product_id")
        .annotate(score=Count("user_id", distinct=True))
        .order_by("-score")
        .values_list("product_id", flat=True)[: limit * 2]
    )

    category_ids = Product.objects.filter(pk__in=interacted_ids).values_list("category_id", flat=True)
    content_ids = list(
        Product.objects.filter(category_id__in=category_ids, status=Product.Status.PUBLISHED)
        .exclude(pk__in=interacted_ids)
        .values_list("id", flat=True)[: limit * 2]
    )

    ordered_ids = []
    for product_id in collaborative_ids + content_ids:
        if product_id not in ordered_ids:
            ordered_ids.append(product_id)
        if len(ordered_ids) >= limit:
            break

    if len(ordered_ids) < limit:
        for product in get_best_sellers(limit=limit * 2):
            if product.id not in ordered_ids and product.id not in interacted_ids:
                ordered_ids.append(product.id)
            if len(ordered_ids) >= limit:
                break

    products_by_id = Product.objects.filter(pk__in=ordered_ids, status=Product.Status.PUBLISHED).in_bulk()
    return [products_by_id[pid] for pid in ordered_ids if pid in products_by_id]


def get_trending_products(days=7, limit=10):
    since = timezone.now() - timedelta(days=days)
    return (
        Product.objects.filter(status=Product.Status.PUBLISHED, views__viewed_at__gte=since)
        .annotate(view_count=Count("views"))
        .order_by("-view_count")[:limit]
    )


def get_best_sellers(days=None, limit=10):
    items = OrderItem.objects.filter(order__status__in=PURCHASABLE_STATUSES)
    if days is not None:
        since = timezone.now() - timedelta(days=days)
        items = items.filter(order__created_at__gte=since)
    ranked = items.values("product_id").annotate(units_sold=Sum("quantity")).order_by("-units_sold")[:limit]
    ids_in_order = [row["product_id"] for row in ranked]
    products_by_id = Product.objects.in_bulk(ids_in_order)
    return [products_by_id[pid] for pid in ids_in_order if pid in products_by_id]


def vendor_analytics(store):
    orders = Order.objects.filter(store=store)
    completed = orders.filter(status__in=PURCHASABLE_STATUSES)
    revenue = completed.aggregate(total=Sum("total_amount"))["total"] or 0

    now = timezone.now()
    window_start = (now - relativedelta(months=5)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_by_month = {
        row["month"].strftime("%Y-%m"): row["total"]
        for row in completed.filter(created_at__gte=window_start)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("total_amount"))
    }
    monthly_sales = []
    for i in range(5, -1, -1):
        month_date = (now - relativedelta(months=i)).replace(day=1)
        monthly_sales.append({
            "label": month_date.strftime("%b"),
            "total": float(revenue_by_month.get(month_date.strftime("%Y-%m"), 0) or 0),
        })

    views_count = ProductView.objects.filter(product__store=store).count()
    conversion_rate = round(completed.count() / views_count * 100, 1) if views_count else 0

    return {
        "revenue": revenue,
        "sales_count": completed.count(),
        "total_orders": orders.count(),
        "average_order_value": completed.aggregate(avg=Avg("total_amount"))["avg"] or 0,
        "pending_orders": orders.filter(status=Order.Status.PENDING).count(),
        "product_count": Product.objects.filter(store=store).count(),
        "customer_count": orders.values("customer_id").distinct().count(),
        "views_count": views_count,
        "conversion_rate": conversion_rate,
        "monthly_sales": monthly_sales,
    }


def admin_analytics():
    orders = Order.objects.filter(status__in=PURCHASABLE_STATUSES)
    platform_revenue = orders.aggregate(total=Sum("total_amount"))["total"] or 0
    top_vendor_rows = (
        orders.values("store__id", "store__name")
        .annotate(revenue=Sum("total_amount"))
        .order_by("-revenue")[:10]
    )
    return {
        "platform_revenue": platform_revenue,
        "total_orders": orders.count(),
        "total_vendors": Store.objects.filter(status=Store.Status.APPROVED).count(),
        "top_vendors": list(top_vendor_rows),
        "best_sellers": [
            {"id": p.id, "name": p.name, "sku": p.sku} for p in get_best_sellers(limit=10)
        ],
    }


def sales_report(store=None, date_from=None, date_to=None):
    orders = Order.objects.all()
    if store is not None:
        orders = orders.filter(store=store)
    if date_from is not None:
        orders = orders.filter(created_at__gte=date_from)
    if date_to is not None:
        orders = orders.filter(created_at__lte=date_to)
    by_status = orders.values("status").annotate(count=Count("id"), total=Sum("total_amount"))
    return {
        "total_orders": orders.count(),
        "total_revenue": orders.filter(status__in=PURCHASABLE_STATUSES).aggregate(
            total=Sum("total_amount")
        )["total"]
        or 0,
        "by_status": list(by_status),
    }


def inventory_report():
    stocks = Stock.objects.select_related("product")
    total_stock_value = sum((s.quantity * s.product.price for s in stocks), 0)
    return {
        "total_products_stocked": stocks.count(),
        "total_units_on_hand": stocks.aggregate(total=Sum("quantity"))["total"] or 0,
        "low_stock_count": stocks.low_stock().count(),
        "out_of_stock_count": stocks.out_of_stock().count(),
        "estimated_stock_value": total_stock_value,
    }


def vendor_report():
    rows = (
        Store.objects.filter(status=Store.Status.APPROVED)
        .annotate(order_count=Count("orders"), revenue=Sum("orders__total_amount"))
        .values("id", "name", "order_count", "revenue")
        .order_by("-revenue")
    )
    return list(rows)


def product_report(store=None):
    items = OrderItem.objects.filter(order__status__in=PURCHASABLE_STATUSES)
    if store is not None:
        items = items.filter(order__store=store)
    rows = (
        items.values("product_id", "product_name")
        .annotate(units_sold=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity")))
        .order_by("-revenue")
    )
    return list(rows)


def tax_report(date_from=None, date_to=None):
    orders = Order.objects.filter(status__in=PURCHASABLE_STATUSES)
    if date_from is not None:
        orders = orders.filter(created_at__gte=date_from)
    if date_to is not None:
        orders = orders.filter(created_at__lte=date_to)
    return {
        "orders_counted": orders.count(),
        "total_tax_collected": orders.aggregate(total=Sum("tax_amount"))["total"] or 0,
    }


def refund_report():
    refunds = PaymentTransaction.objects.filter(status=PaymentTransaction.Status.REFUNDED)
    return {
        "refund_count": refunds.count(),
        "total_refunded": refunds.aggregate(total=Sum("amount"))["total"] or 0,
    }

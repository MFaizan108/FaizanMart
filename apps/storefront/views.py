from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Sum
from django.shortcuts import get_object_or_404, render

from apps.catalog.models import Brand, Category, Product
from apps.inventory.models import Stock
from apps.marketing import services as marketing_services
from apps.orders.models import Order
from apps.payments import services as payments_services
from apps.reviews.models import Review, WishlistItem
from apps.support.models import FAQ


RECENTLY_VIEWED_SESSION_KEY = "recently_viewed_product_ids"
RECENTLY_VIEWED_LIMIT = 8


def _record_recently_viewed(request, product_id):
    seen = request.session.get(RECENTLY_VIEWED_SESSION_KEY, [])
    seen = [pid for pid in seen if pid != product_id]
    seen.insert(0, product_id)
    request.session[RECENTLY_VIEWED_SESSION_KEY] = seen[:RECENTLY_VIEWED_LIMIT]


def _recently_viewed_products(request, exclude_id=None):
    ids = [pid for pid in request.session.get(RECENTLY_VIEWED_SESSION_KEY, []) if pid != exclude_id]
    if not ids:
        return []
    products = Product.objects.filter(id__in=ids, status=Product.Status.PUBLISHED).select_related(
        "category", "brand", "store"
    ).prefetch_related("images")
    by_id = {p.id: p for p in products}
    return [by_id[pid] for pid in ids if pid in by_id]


def _wishlisted_ids(request, products):
    if not request.user.is_authenticated:
        return set()
    product_ids = [p.id for p in products]
    return set(
        WishlistItem.objects.filter(customer=request.user, product_id__in=product_ids)
        .values_list("product_id", flat=True)
    )


def _decorate_products_for_cards(products):
    """Attaches the extra bits the product card needs (rating, review count, discount
    percentage, in-stock flag) as plain attributes, computed in bulk rather than once per
    product — cheap enough for a handful of cards, and keeps the template dict-lookup-free."""
    products = list(products)
    if not products:
        return products

    ids = [p.id for p in products]

    rating_map = {
        row["product_id"]: row
        for row in Review.objects.filter(product_id__in=ids)
        .values("product_id")
        .annotate(avg=Avg("rating"), count=Count("id"))
    }

    tracked_ids = [p.id for p in products if p.product_type != Product.ProductType.DIGITAL]
    stock_map = {
        row["product_id"]: row["available"]
        for row in Stock.objects.filter(product_id__in=tracked_ids)
        .values("product_id")
        .annotate(available=Sum(F("quantity") - F("reserved_quantity")))
    }

    for product in products:
        rating = rating_map.get(product.id)
        product.card_avg_rating = round(rating["avg"], 1) if rating else 0
        product.card_review_count = rating["count"] if rating else 0

        if product.compare_at_price and product.compare_at_price > product.price:
            product.card_discount_pct = round(
                (product.compare_at_price - product.price) / product.compare_at_price * 100
            )
        else:
            product.card_discount_pct = 0

        if product.product_type == Product.ProductType.DIGITAL or product.id not in stock_map:
            product.card_in_stock = True  # untracked/digital = unlimited, matches apps.cart.services
        else:
            product.card_in_stock = stock_map[product.id] > 0

    return products


def home(request):
    categories = Category.objects.filter(is_active=True)
    banners = list(marketing_services.get_active_banners(position="home_hero"))
    promo_banner = marketing_services.get_active_banners(position="home_secondary").first()
    featured = list(marketing_services.get_featured_products(limit=8))

    products_qs = Product.objects.filter(status=Product.Status.PUBLISHED).select_related(
        "category", "brand", "store"
    ).prefetch_related("images")

    if featured:
        featured_ids = [item.product_id for item in featured]
        spotlight = list(products_qs.filter(id__in=featured_ids))
        spotlight_label = "Featured products"
    else:
        spotlight = list(products_qs.order_by("-created_at")[:8])
        spotlight_label = "New arrivals"

    new_arrivals = list(products_qs.order_by("-created_at")[:8])
    best_sellers = list(products_qs.order_by("-created_at")[8:16]) or new_arrivals[:4]

    flash_sale = marketing_services.get_live_flash_sales().prefetch_related("items__product").first()
    flash_items = list(flash_sale.items.all()) if flash_sale else []
    flash_products = [item.product for item in flash_items]
    sale_price_by_product = {item.product_id: item.sale_price for item in flash_items}
    discount_by_product = {item.product_id: item.discount_percentage for item in flash_items}

    recently_viewed = _recently_viewed_products(request)

    all_products = spotlight + new_arrivals + best_sellers + flash_products + recently_viewed
    _decorate_products_for_cards(all_products)
    for product in flash_products:
        product.card_discount_pct = round(discount_by_product[product.id])
        product.flash_sale_price = sale_price_by_product[product.id]

    wishlisted_ids = _wishlisted_ids(request, all_products)

    return render(request, "storefront/home.html", {
        "categories": categories,
        "banners": banners,
        "spotlight_products": spotlight,
        "spotlight_label": spotlight_label,
        "new_arrivals": new_arrivals,
        "best_sellers": best_sellers,
        "flash_sale": flash_sale,
        "flash_products": flash_products,
        "recently_viewed": recently_viewed,
        "promo_banner": promo_banner,
        "wishlisted_ids": wishlisted_ids,
    })


def product_list(request):
    categories = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related("children")
    brands = Brand.objects.filter(is_active=True).order_by("name")
    return render(request, "storefront/product_list.html", {
        "categories": categories,
        "brands": brands,
        "query": request.GET.get("q", ""),
        "selected_category": request.GET.get("category", ""),
        "selected_brand": request.GET.get("brand", ""),
        "min_price": request.GET.get("min_price", ""),
        "max_price": request.GET.get("max_price", ""),
        "min_rating": request.GET.get("min_rating", ""),
        "in_stock": request.GET.get("in_stock", ""),
        "sort": request.GET.get("sort", ""),
    })


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("store", "category", "brand").prefetch_related(
            "tags", "images", "variants", "specifications"
        ),
        pk=pk,
        status=Product.Status.PUBLISHED,
    )
    reviews = Review.objects.filter(product=product).select_related("customer")
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
    images = list(product.images.all())
    primary_image = next((img for img in images if img.is_primary), None) or (images[0] if images else None)
    is_wishlisted = bool(_wishlisted_ids(request, [product]))

    related = list(
        Product.objects.filter(status=Product.Status.PUBLISHED, category=product.category)
        .exclude(id=product.id)
        .select_related("category", "brand", "store")
        .prefetch_related("images")[:4]
    )
    _decorate_products_for_cards(related)

    recently_viewed = _recently_viewed_products(request, exclude_id=product.id)
    _decorate_products_for_cards(recently_viewed)
    _record_recently_viewed(request, product.id)

    return render(request, "storefront/product_detail.html", {
        "product": product,
        "reviews": reviews,
        "avg_rating": avg_rating,
        "primary_image": primary_image,
        "is_wishlisted": is_wishlisted,
        "related_products": related,
        "recently_viewed": recently_viewed,
        "wishlisted_ids": _wishlisted_ids(request, related + recently_viewed),
    })


def cart(request):
    return render(request, "storefront/cart.html")


@login_required
def wishlist(request):
    return render(request, "storefront/wishlist.html")


@login_required
def checkout(request):
    return render(request, "storefront/checkout.html")


@login_required
def order_success(request):
    return render(request, "storefront/order_success.html")


@login_required
def account_dashboard(request):
    orders = Order.objects.filter(customer=request.user)
    pending_statuses = [
        Order.Status.PENDING, Order.Status.PROCESSING, Order.Status.PACKED, Order.Status.SHIPPED,
    ]
    wallet = payments_services.get_or_create_wallet(request.user)
    recent_orders = orders.select_related("store").order_by("-created_at")[:5]
    return render(request, "storefront/account_dashboard.html", {
        "total_orders": orders.count(),
        "pending_orders": orders.filter(status__in=pending_statuses).count(),
        "completed_orders": orders.filter(status=Order.Status.DELIVERED).count(),
        "wallet_balance": wallet.balance,
        "recent_orders": recent_orders,
    })


@login_required
def order_list(request):
    return render(request, "storefront/order_list.html")


@login_required
def order_detail(request, pk):
    return render(request, "storefront/order_detail.html", {"order_id": pk})


@login_required
def notifications(request):
    return render(request, "storefront/notifications.html")


@login_required
def wallet(request):
    return render(request, "storefront/wallet.html")


@login_required
def addresses(request):
    return render(request, "storefront/addresses.html")


def help_center(request):
    faqs = FAQ.objects.filter(is_published=True)
    categories = {}
    for faq in faqs:
        categories.setdefault(faq.category or "General", []).append(faq)
    return render(request, "storefront/help.html", {"faq_groups": categories})

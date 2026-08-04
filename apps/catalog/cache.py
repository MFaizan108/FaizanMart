from django.core.cache import cache

CACHE_TTL = 60 * 10  # 10 minutes

# Only the common, unparameterized case is cached (public, no `parent` filter) — every other
# query-param combination falls through to the database. Keeps invalidation a plain, exact
# key delete instead of needing pattern-matching the built-in Redis cache backend lacks.
PUBLIC_CATEGORY_LIST_KEY = "catalog:categories:public"


def product_detail_key(product_id):
    return f"catalog:product:{product_id}"


def invalidate_product(product_id):
    cache.delete(product_detail_key(product_id))


def invalidate_category_list():
    cache.delete(PUBLIC_CATEGORY_LIST_KEY)

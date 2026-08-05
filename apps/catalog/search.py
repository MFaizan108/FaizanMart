"""Search service built on the ProductDocument Elasticsearch index.

- Full-text + filters: search_products() below.
- Typo correction: the main query uses fuzziness="AUTO" (so "iphon" still matches "iPhone"
  via edit distance) and a separate ES term suggester returns an explicit "did you mean"
  string even when the fuzzy match already found results.
- Smart search: parse_smart_query() is a lightweight heuristic — it strips known Brand and
  Category names out of the raw query text into structured filters (e.g. "nike shoes" ->
  brand=Nike, remaining text "shoes"), rather than a full NLU/LLM parse. Colors are left in
  the free-text query rather than turned into a strict filter, since Product itself has no
  color field (only ProductVariant does) — a color word still helps ranking via the name/
  description match.
- Semantic search: handled at the analyzer level (see ProductDocument's synonym_analyzer),
  not here — "running shoes" matches "joggers" because the index maps them to the same terms.
"""

from apps.catalog.models import Brand, Category

from .documents import ProductDocument

COLOR_WORDS = {
    "black", "white", "red", "blue", "green", "yellow", "grey", "gray",
    "silver", "gold", "pink", "purple", "orange", "brown", "beige", "navy",
}


def parse_smart_query(query_text):
    tokens = query_text.strip().split()
    if not tokens:
        return query_text, {}

    brand_by_name = {b.name.lower(): b.name for b in Brand.objects.filter(is_active=True)}
    category_by_name = {c.name.lower(): c.name for c in Category.objects.filter(is_active=True)}

    filters = {}
    remaining = []
    for token in tokens:
        clean = token.strip(",.").lower()
        if clean in brand_by_name and "brand" not in filters:
            filters["brand"] = brand_by_name[clean]
            continue
        if clean in category_by_name and "category" not in filters:
            filters["category"] = category_by_name[clean]
            continue
        remaining.append(token)

    return " ".join(remaining), filters


SORT_FIELDS = {
    "newest": {"created_at": {"order": "desc"}},
    "price_asc": {"price": {"order": "asc"}},
    "price_desc": {"price": {"order": "desc"}},
    "rating": {"avg_rating": {"order": "desc"}},
    "popular": {"review_count": {"order": "desc"}},
}


def search_products(
    *, query="", category=None, brand=None, store=None, min_price=None, max_price=None,
    min_rating=None, in_stock_only=False, sort=None, page=1, page_size=20,
):
    search = ProductDocument.search().filter("term", status="published")

    smart_filters = {}
    suggestion = None
    if query:
        remaining_text, smart_filters = parse_smart_query(query)
        search_text = remaining_text.strip() or query
        search = search.query(
            "multi_match",
            query=search_text,
            fields=["name^3", "description", "brand_name^2", "category_name^2", "tags"],
            fuzziness="AUTO",
        )
        search = search.suggest("did_you_mean", search_text, term={"field": "name"})

    effective_brand = brand or smart_filters.get("brand")
    effective_category = category or smart_filters.get("category")

    if effective_category:
        search = search.filter("term", category_name__raw=effective_category)
    if effective_brand:
        search = search.filter("term", brand_name__raw=effective_brand)
    if store is not None:
        search = search.filter("term", store_id=int(store))
    if min_price is not None:
        search = search.filter("range", price={"gte": float(min_price)})
    if max_price is not None:
        search = search.filter("range", price={"lte": float(max_price)})
    if min_rating is not None:
        search = search.filter("range", avg_rating={"gte": float(min_rating)})
    if in_stock_only:
        search = search.filter("term", is_available=True)

    if sort in SORT_FIELDS:
        search = search.sort(SORT_FIELDS[sort])

    start = (page - 1) * page_size
    search = search[start:start + page_size]

    response = search.execute()

    if query and response.suggest and "did_you_mean" in response.suggest:
        for entry in response.suggest["did_you_mean"]:
            for option in entry.options:
                if option.text.lower() != query.lower():
                    suggestion = option.text
                    break
            if suggestion:
                break

    return {
        "count": response.hits.total.value,
        "results": [hit.to_dict() | {"id": hit.meta.id} for hit in response],
        "did_you_mean": suggestion,
        "applied_filters": {"brand": effective_brand, "category": effective_category},
    }

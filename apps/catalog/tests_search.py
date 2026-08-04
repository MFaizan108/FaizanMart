"""Elasticsearch-backed search tests.

ELASTICSEARCH_DSL_AUTOSYNC is off for the whole test run (see FaizanMart/settings/test.py) —
otherwise every Product any of the ~180 other tests across the suite creates would leak a
permanent document into the real "products" index, since ES indexing signals fire on save()
regardless of whether the Postgres transaction that save() happened in ever commits. So here
we index/deindex explicitly via `ProductDocument().update(instance[, action="delete"])`,
which isn't gated by that flag, instead of relying on signals at all.

These tests talk to the real Elasticsearch instance (see docker-compose.yml / .env
ELASTICSEARCH_URL) — there's no in-memory fake for it the way DummyCache stands in for
Redis elsewhere in this test suite.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.vendors.models import Store

from .documents import ProductDocument
from .models import Brand, Category, Product
from .search import parse_smart_query, search_products

User = get_user_model()


class SmartQueryParsingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Shoes")
        self.brand = Brand.objects.create(name="Nike")

    def test_extracts_known_brand_and_category(self):
        remaining, filters = parse_smart_query("nike shoes")
        self.assertEqual(filters, {"brand": "Nike", "category": "Shoes"})
        self.assertEqual(remaining, "")

    def test_leaves_unknown_words_in_remaining_text(self):
        remaining, filters = parse_smart_query("black nike shoes size 10")
        self.assertEqual(filters["brand"], "Nike")
        self.assertEqual(filters["category"], "Shoes")
        self.assertIn("black", remaining)
        self.assertIn("size", remaining)

    def test_no_known_terms_returns_original_text_untouched(self):
        remaining, filters = parse_smart_query("something completely unrelated")
        self.assertEqual(filters, {})
        self.assertEqual(remaining, "something completely unrelated")

    def test_empty_query(self):
        remaining, filters = parse_smart_query("")
        self.assertEqual(filters, {})


class ProductSearchIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Shoes")
        self.brand = Brand.objects.create(name="Nike")
        vendor = User.objects.create_user(
            email="searchvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=vendor, name="Search Store", status=Store.Status.APPROVED)
        self.products = []

    def tearDown(self):
        for product in self.products:
            ProductDocument().update(product, action="delete")
            product.delete()
        ProductDocument._index.refresh()

    def _make_product(self, **overrides):
        defaults = dict(
            store=self.store, category=self.category, price="50.00", status=Product.Status.PUBLISHED,
        )
        defaults.update(overrides)
        product = Product.objects.create(**defaults)
        self.products.append(product)
        ProductDocument().update(product)
        ProductDocument._index.refresh()
        return product

    # Product names use a distinctive "Zzq" marker so fuzzy/synonym matching can't
    # accidentally collide with unrelated real data sitting in the same shared dev index —
    # assertions check the expected product is present rather than an exact total count,
    # since this index isn't exclusively owned by the test run the way the Postgres test
    # database is.

    def test_full_text_search_matches_name(self):
        self._make_product(name="Zzq Wireless Bluetooth Mouse", sku="SRCH-1")
        results = search_products(query="zzq bluetooth mouse")
        names = {r["name"] for r in results["results"]}
        self.assertIn("Zzq Wireless Bluetooth Mouse", names)

    def test_typo_tolerant_search_still_matches(self):
        self._make_product(name="Zzq Wireless Mouse", sku="SRCH-2")
        results = search_products(query="zzq wireles muose")
        names = {r["name"] for r in results["results"]}
        self.assertIn("Zzq Wireless Mouse", names)

    def test_did_you_mean_suggestion_returned(self):
        self._make_product(name="Zzq Wireless Mouse", sku="SRCH-3")
        results = search_products(query="zzq wireles")
        self.assertIsNotNone(results["did_you_mean"])

    def test_smart_search_extracts_brand_filter(self):
        self._make_product(name="Zzq Running Shoes", brand=self.brand, sku="SRCH-4")
        other_brand = Brand.objects.create(name="Adidas")
        self._make_product(name="Zzq Running Shoes", brand=other_brand, sku="SRCH-5")

        results = search_products(query="nike zzq shoes")
        names = {r["name"] for r in results["results"]}
        self.assertEqual(results["applied_filters"]["brand"], "Nike")
        self.assertEqual(len([n for n in names if n == "Zzq Running Shoes"]), 1)

    def test_synonym_semantic_match_without_shared_words(self):
        self._make_product(name="Zzq Comfort Joggers Pro", sku="SRCH-6")
        results = search_products(query="zzq sports shoes")
        names = {r["name"] for r in results["results"]}
        self.assertIn("Zzq Comfort Joggers Pro", names)

    def test_price_range_filter(self):
        self._make_product(name="Zzq Cheap Item", price="10.00", sku="SRCH-7")
        self._make_product(name="Zzq Expensive Item", price="500.00", sku="SRCH-8")

        results = search_products(query="zzq", min_price=100, max_price=1000)
        names = {r["name"] for r in results["results"]}
        self.assertIn("Zzq Expensive Item", names)
        self.assertNotIn("Zzq Cheap Item", names)

    def test_unpublished_products_are_excluded(self):
        self._make_product(name="Zzq Draft Item", sku="SRCH-9", status=Product.Status.DRAFT)
        results = search_products(query="zzq draft item")
        names = {r["name"] for r in results["results"]}
        self.assertNotIn("Zzq Draft Item", names)


class ProductSearchApiTests(TransactionTestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Gear")
        vendor = User.objects.create_user(
            email="searchapivendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=vendor, name="Search API Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=self.store, category=self.category, name="Zzq Searchable Gadget", price="30.00",
            status=Product.Status.PUBLISHED, sku="SRCH-API-1",
        )
        ProductDocument().update(self.product)
        ProductDocument._index.refresh()
        self.client = APIClient()

    def tearDown(self):
        ProductDocument().update(self.product, action="delete")
        self.product.delete()
        ProductDocument._index.refresh()

    def test_search_endpoint_is_public_and_returns_results(self):
        response = self.client.get(reverse("catalog_api:product-search"), {"q": "zzq searchable gadget"})
        self.assertEqual(response.status_code, 200)
        names = {r["name"] for r in response.data["results"]}
        self.assertIn("Zzq Searchable Gadget", names)

    def test_search_endpoint_rejects_non_integer_pagination(self):
        response = self.client.get(reverse("catalog_api:product-search"), {"page": "abc"})
        self.assertEqual(response.status_code, 400)

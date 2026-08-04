"""Tests mock every Ollama HTTP call (via requests.post) — the point being verified isn't
"does Qwen work" (that's Ollama's problem, and settings/test.py points OLLAMA_URL at a
dead port so any unmocked call fails loudly), it's "does this module only ever put real,
DB-backed products in front of the user, no matter what the model does or doesn't say."

The one exception is the search-grounding tests, which need a real Elasticsearch document
to search for — see apps/catalog/tests_search.py for why TransactionTestCase + explicit
ProductDocument().update() is the pattern here (ELASTICSEARCH_DSL_AUTOSYNC is off).
"""

from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.catalog.documents import ProductDocument
from apps.catalog.models import Category, Product
from apps.vendors.models import Store

from . import services

User = get_user_model()


def _tool_call_message(**kwargs):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "search_products", "arguments": kwargs}}],
    }


class AssistantServiceGroundingTests(TransactionTestCase):
    """Exercises the real search_products() path end-to-end with a real ES document, so
    "products in the response actually came from the database" is a genuine assertion."""

    def setUp(self):
        self.category = Category.objects.create(name="Laptops")
        vendor = User.objects.create_user(
            email="assistantvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=vendor, name="Assistant Store", status=Store.Status.APPROVED)
        self.product = Product.objects.create(
            store=self.store, category=self.category, name="Zzq Programming Laptop 16GB",
            price="145000.00", status=Product.Status.PUBLISHED, sku="AST-1",
        )
        ProductDocument().update(self.product)
        ProductDocument._index.refresh()

    def tearDown(self):
        ProductDocument().update(self.product, action="delete")
        self.product.delete()
        ProductDocument._index.refresh()

    @patch("apps.assistant.services.requests.post")
    def test_tool_call_grounds_reply_in_real_product(self, mock_post):
        mock_post.side_effect = [
            _fake_response(_tool_call_message(query="zzq programming laptop", max_price=150000)),
            _fake_response({"role": "assistant", "content": "Found a great match for you."}),
        ]

        result = services.ask_shopping_assistant("zzq laptop under 150000 for programming")

        self.assertTrue(result["ai_generated"])
        matches = [p for p in result["products"] if p["name"] == "Zzq Programming Laptop 16GB"]
        self.assertEqual(len(matches), 1)
        # Confirms the id tagged onto the result is the real product's id, not something the
        # mocked LLM output could have injected — the product list came from a genuine
        # search_products() call, not model-authored text.
        self.assertEqual(matches[0]["id"], str(self.product.id))

    @patch("apps.assistant.services.requests.post")
    def test_model_skipping_the_tool_call_still_gets_grounded(self, mock_post):
        # The model just answers in prose without calling search_products at all — the
        # service must not trust that text; it has to search on the raw query itself.
        mock_post.side_effect = [
            _fake_response({"role": "assistant", "content": "Sure, we have great laptops!"}),
        ]

        result = services.ask_shopping_assistant("zzq programming laptop")

        self.assertTrue(mock_post.call_count == 1)  # no second round-trip was made
        names = {p["name"] for p in result["products"]}
        self.assertIn("Zzq Programming Laptop 16GB", names)

    @patch("apps.assistant.services.requests.post")
    def test_ollama_unreachable_falls_back_to_direct_search(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("no route to host")

        result = services.ask_shopping_assistant("zzq programming laptop")

        self.assertFalse(result["ai_generated"])
        names = {p["name"] for p in result["products"]}
        self.assertIn("Zzq Programming Laptop 16GB", names)
        self.assertIn("temporarily unavailable", result["message"])

    @patch("apps.assistant.services.requests.post")
    def test_roman_urdu_query_gets_a_roman_urdu_language_directive(self, mock_post):
        mock_post.side_effect = [
            _fake_response(_tool_call_message(query="programming laptop")),
            _fake_response({"role": "assistant", "content": "Aapke liye laptops mil gaye hain!"}),
        ]

        services.ask_shopping_assistant("mujhe zzq programming laptop chahiye")

        first_call_payload = mock_post.call_args_list[0].kwargs["json"]
        system_content = first_call_payload["messages"][0]["content"]
        self.assertIn("Roman Urdu", system_content)
        self.assertNotIn("Urdu script (اردو)", system_content)


class AssistantServiceUnitTests(TestCase):
    def test_empty_query_short_circuits_without_calling_ollama(self):
        with patch("apps.assistant.services.requests.post") as mock_post:
            result = services.ask_shopping_assistant("   ")
        mock_post.assert_not_called()
        self.assertEqual(result["products"], [])

    def test_sanitize_tool_args_drops_unknown_and_malformed_fields(self):
        cleaned = services._sanitize_tool_args(
            {"query": "shoes", "max_price": "not-a-number", "min_price": "500", "evil": "DROP TABLE"}
        )
        self.assertEqual(cleaned, {"query": "shoes", "min_price": 500.0})

    def test_sanitize_tool_args_parses_json_string_arguments(self):
        cleaned = services._sanitize_tool_args('{"query": "shoes", "brand": "Nike"}')
        self.assertEqual(cleaned, {"query": "shoes", "brand": "Nike"})

    def test_sanitize_tool_args_rejects_non_dict_non_json(self):
        self.assertEqual(services._sanitize_tool_args("not json"), {})
        self.assertEqual(services._sanitize_tool_args(None), {})

    def test_extract_inline_tool_call_recovers_from_garbled_text(self):
        # Seen in practice: a quantized model sometimes writes the tool call out as plain
        # text instead of using Ollama's structured tool_calls field.
        garbled = (
            ' Ronaldo\n{"name": "search_products", "arguments": '
            '{"query": "shoes", "max_price": 5000}}\n</tool_call>'
        )
        self.assertEqual(
            services._extract_inline_tool_call(garbled), {"query": "shoes", "max_price": 5000}
        )

    def test_extract_inline_tool_call_returns_none_for_plain_prose(self):
        self.assertIsNone(services._extract_inline_tool_call("Sure, here are some laptops for you!"))
        self.assertIsNone(services._extract_inline_tool_call(""))
        self.assertIsNone(services._extract_inline_tool_call(None))


class LanguageDetectionTests(TestCase):
    """The model proved unreliable at detecting the customer's language on its own (see
    services.py module docstring) — this is the deterministic replacement, and it's the
    part that actually decides what the customer sees, so it's worth pinning down directly."""

    def test_detects_urdu_script(self):
        self.assertIn("Urdu script", services._detect_reply_language("مجھے لیپ ٹاپ چاہیے"))

    def test_detects_roman_urdu(self):
        label = services._detect_reply_language("mujhe 150000 tak ka laptop chahiye programming k liye")
        self.assertIn("Roman Urdu", label)

    def test_detects_english_by_default(self):
        label = services._detect_reply_language("I need a laptop under 150000 for programming")
        self.assertEqual(label, "English")

    def test_single_stray_roman_urdu_word_does_not_flip_english_to_roman_urdu(self):
        # One loanword-ish overlap shouldn't be enough to misclassify a clearly English query.
        label = services._detect_reply_language("show me a laptop for programming")
        self.assertEqual(label, "English")

    def test_empty_query_defaults_to_english(self):
        self.assertEqual(services._detect_reply_language(""), "English")


class AssistantApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_query_is_required(self):
        response = self.client.post(reverse("assistant_api:query"), {})
        self.assertEqual(response.status_code, 400)

    @patch("apps.assistant.api_views.services.ask_shopping_assistant")
    def test_endpoint_is_public_and_returns_service_result(self, mock_ask):
        mock_ask.return_value = {
            "message": "Here you go.", "products": [], "applied_filters": {}, "ai_generated": True,
        }
        response = self.client.post(reverse("assistant_api:query"), {"query": "laptop"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Here you go.")
        mock_ask.assert_called_once_with("laptop")


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "assistant-rate-limit-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AssistantThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    @patch("apps.assistant.api_views.services.ask_shopping_assistant")
    def test_assistant_endpoint_is_throttled_after_fifteen_per_minute(self, mock_ask):
        mock_ask.return_value = {"message": "ok", "products": [], "applied_filters": {}, "ai_generated": False}
        url = reverse("assistant_api:query")

        for _ in range(15):
            response = self.client.post(url, {"query": "laptop"})
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(url, {"query": "laptop"})
        self.assertEqual(response.status_code, 429)


def _fake_response(message_dict):
    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": message_dict}

    return _FakeResponse()

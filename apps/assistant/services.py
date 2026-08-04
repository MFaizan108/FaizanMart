"""AI shopping assistant: natural-language query -> real inventory -> grounded reply.

The one rule this whole module exists to enforce: the model is never trusted to state
facts about products from its own memory. It only gets to *call a tool* that runs the
real Elasticsearch-backed apps.catalog.search.search_products() against the live
database, and its final reply is generated with those actual results as its only source
of product data. Concretely:

    1. Send the user's query to Qwen (via Ollama) with one tool it can call:
       search_products (mirrors search_products()'s own parameters).
    2. Whatever the model asks for, actually run it against Elasticsearch/Postgres —
       this is the only place real product data enters the conversation.
    3. Feed the real results back to the model and ask it for a reply. The model is
       explicitly forbidden from naming a specific product/price/spec itself — in testing,
       even with real results in front of it, a 7B quantized model would occasionally
       invent a plausible-sounding product that wasn't actually in the results (e.g.
       "Dell Inspiron 15 - Rs. 140,000" when nothing by that name existed). So its reply is
       only ever a short generic intro/closing line; the actual product facts shown to the
       caller always come from the structured `products` list, never from the model's prose.

Multi-language: the customer can write in English, Urdu script, or Roman Urdu (Urdu
spelled with Latin letters), in any turn. Which one to reply in is decided in *code*
(_detect_reply_language), not left for the model to infer — testing showed the model
could follow an explicit "reply in Roman Urdu" instruction reliably, but was NOT reliable
at first detecting the input language itself and stayed correct only when told outright.

If Ollama can't be reached at all (not installed, not running, model not pulled), the
caller falls back to running search_products() directly with the raw query text — no
LLM step, but still real, grounded results instead of an error page.
"""

import json
import logging
import re

import requests
from django.conf import settings

from apps.catalog.search import search_products

logger = logging.getLogger(__name__)

URDU_SCRIPT_RE = re.compile(r"[؀-ۿ]")

# A small marker-word list is enough to reliably flag Roman Urdu (Urdu spelled with Latin
# letters) vs. plain English — full linguistic detection isn't needed, just a confident
# yes/no on "does this look like Urdu written in English letters".
ROMAN_URDU_MARKERS = {
    "mujhe", "chahiye", "chahye", "chahta", "chahti", "hai", "hain", "kya", "kyu", "kyun",
    "kitna", "kitne", "kitni", "wala", "wali", "sasta", "sasti", "sastay", "acha", "accha",
    "dikhao", "dikha", "tak", "ka", "ki", "ke", "k", "aur", "nahi", "nahin", "mein", "main",
    "se", "ko", "pasand", "aaya", "aayi", "aap", "aapka", "aapke", "aapki", "liye", "hoon",
    "kar", "karo", "sakta", "sakti", "batao", "bata", "chaiye", "de", "do", "diya",
    "milega", "milegi", "mil", "gaya", "gayi",
}


def _detect_reply_language(query):
    """Decides the reply language/script in code rather than leaving it to the model to
    infer — in testing, a 7B quantized model reliably followed an explicit "write in X"
    instruction but was NOT reliable at first detecting the input language itself and
    consistently sticking with it turn to turn, so that decision is made here instead."""
    if URDU_SCRIPT_RE.search(query):
        return "Urdu script (اردو) — write the entire reply in the Urdu alphabet only, no Latin letters at all"
    tokens = re.findall(r"[a-zA-Z']+", query.lower())
    marker_hits = sum(1 for token in tokens if token in ROMAN_URDU_MARKERS)
    if tokens and marker_hits / len(tokens) >= 0.2:
        return "Roman Urdu — Urdu words spelled out with Latin/English letters, e.g. 'mujhe chahiye'"
    return "English"


SYSTEM_PROMPT = (
    "You are the FaizanMart shopping assistant. A customer will describe what they're "
    "looking for in their own words.\n\n"
    "LANGUAGE RULE — this is about SCRIPT (the alphabet used), not just language:\n"
    "  - English input (Latin letters, English words) -> reply in English, Latin letters.\n"
    "  - Roman Urdu input (Urdu words spelled out in Latin/English letters, e.g. 'mujhe "
    "laptop chahiye', 'sasta wala dikhao', 'kitne ka hai') -> reply in Roman Urdu, using "
    "ONLY Latin/English letters. Do NOT switch to the Urdu alphabet (اردو رسم الخط) even "
    "though the words are Urdu — keep writing Urdu words with English letters, exactly "
    "like the customer did.\n"
    "  - Urdu-script input (اردو حروف, e.g. 'مجھے لیپ ٹاپ چاہیے') -> reply in Urdu script.\n"
    "Whichever of these three the customer used, stay in that exact one for the whole "
    "reply — never mix scripts in one reply, never switch partway, never translate into "
    "English 'for clarity', and keep matching it on every later turn of the conversation "
    "too, not just the first.\n"
    "Style examples (script only — not real inventory, never copy their wording):\n"
    "  1) English, results found -> \"I found some laptops that match your budget — take "
    "a look below!\"\n"
    "  2) Roman Urdu, results found -> \"Aapke budget ke mutabiq kuch laptops mil gaye "
    "hain — neeche dekh lijiye!\"\n"
    "  3) Urdu-script, NO results found -> \"معذرت، اس وقت ایسی کوئی پروڈکٹ دستیاب نہیں "
    "ہے۔ براہ کرم اپنی تلاش وسیع کریں۔\"\n\n"
    "Call the search_products tool to find real matching products before saying anything "
    "about what's available. Extract useful filters (budget as max_price/min_price, "
    "brand, category) from the query when they're clearly implied. The tool's `query` "
    "argument must always be in English regardless of what language the customer used "
    "(the catalog itself is indexed in English), but this is only for the tool call — "
    "your reply text to the customer still follows the LANGUAGE RULE above.\n\n"
    "CRITICAL — after you receive the tool's results, your reply must be ONLY a short, "
    "friendly one- or two-sentence intro or closing remark (in the customer's language). "
    "The actual product names/prices are shown to the customer separately by the app, not "
    "by you, so your reply must NEVER contain a specific product name, price, brand, or "
    "spec — not even ones from the real results. If you name or price anything yourself, "
    "even a real one, you are doing it wrong. Just say, generically, that you found some "
    "matches (or didn't) and point them to the list. If the results are empty, say so "
    "plainly (in the customer's language) and suggest they broaden their search."
)

SEARCH_PRODUCTS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": "Search FaizanMart's real product catalog. Always call this before recommending anything.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text description of the product/use-case, IN ENGLISH regardless of what "
                        "language the customer wrote in (e.g. 'laptop for programming')."
                    ),
                },
                "category": {"type": "string", "description": "Product category name, if clearly implied."},
                "brand": {"type": "string", "description": "Brand name, if clearly implied."},
                "min_price": {"type": "number", "description": "Minimum budget, if the customer gave one."},
                "max_price": {"type": "number", "description": "Maximum budget, if the customer gave one."},
                "min_rating": {"type": "number", "description": "Minimum star rating (1-5), if requested."},
                "in_stock_only": {"type": "boolean", "description": "True if the customer wants in-stock items only."},
            },
            "required": ["query"],
        },
    },
}

MAX_PRODUCTS_RETURNED = 8

# Smaller/quantized models don't always populate Ollama's structured tool_calls field —
# sometimes they write the tool call out as plain JSON text in `content` instead (seen in
# practice with qwen2.5:7b-q4). This recognizes that shape so it's still treated as a real
# tool call rather than silently shown to the customer as the final answer.
INLINE_TOOL_CALL_RE = re.compile(
    r'"name"\s*:\s*"search_products"\s*,\s*"arguments"\s*:\s*(\{.*?\})', re.DOTALL
)


def _extract_inline_tool_call(content):
    """Best-effort recovery of a search_products call the model wrote as raw text instead
    of a proper tool_calls entry. Returns the arguments dict, or None if nothing matched."""
    if not content:
        return None
    match = INLINE_TOOL_CALL_RE.search(content)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


class AssistantUnavailableError(Exception):
    """Raised when Ollama can't be reached or returns something unusable."""


def _chat(messages, *, tools=None):
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    try:
        response = requests.post(
            f"{settings.OLLAMA_URL}/api/chat", json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AssistantUnavailableError(str(exc)) from exc

    try:
        return response.json()["message"]
    except (ValueError, KeyError) as exc:
        raise AssistantUnavailableError(f"Unexpected Ollama response shape: {exc}") from exc


def _sanitize_tool_args(raw_args):
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except ValueError:
            return {}
    if not isinstance(raw_args, dict):
        return {}

    args = {}
    query = raw_args.get("query")
    if isinstance(query, str) and query.strip():
        args["query"] = query.strip()[:200]
    for field in ("category", "brand"):
        value = raw_args.get(field)
        if isinstance(value, str) and value.strip():
            args[field] = value.strip()[:100]
    for field in ("min_price", "max_price", "min_rating"):
        value = raw_args.get(field)
        if value is not None:
            try:
                args[field] = float(value)
            except (TypeError, ValueError):
                pass
    if raw_args.get("in_stock_only") is True:
        args["in_stock_only"] = True
    return args


def _serialize_products(results):
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "price": item["price"],
            "brand_name": item.get("brand_name") or "",
            "category_name": item.get("category_name") or "",
            "avg_rating": item.get("avg_rating") or 0.0,
            "is_available": item.get("is_available", False),
        }
        for item in results[:MAX_PRODUCTS_RETURNED]
    ]


def _run_search_tool(tool_args):
    """The only place a product ever gets into the conversation: a real search_products()
    call against Elasticsearch/Postgres, never something the model asserts on its own."""
    search_result = search_products(**tool_args)
    return search_result, _serialize_products(search_result["results"])


def _direct_search_fallback(query, note):
    search_result, products = _run_search_tool({"query": query})
    return {
        "message": note,
        "products": products,
        "applied_filters": search_result["applied_filters"],
        "ai_generated": False,
    }


def ask_shopping_assistant(query):
    """Returns {"message": str, "products": [...], "applied_filters": {...}, "ai_generated": bool}.

    `products` is always grounded in the real catalog. `ai_generated` is False whenever the
    reply is a plain search result rather than an LLM-authored summary (Ollama unreachable,
    or it never called the tool) — the frontend can use that to skip a "chat bubble" style
    render and just show a product grid instead.
    """
    query = (query or "").strip()
    if not query:
        return {"message": "Tell me what you're looking for and I'll search FaizanMart for it.",
                "products": [], "applied_filters": {}, "ai_generated": False}

    language_directive = (
        f"\n\nFOR THIS SPECIFIC CUSTOMER MESSAGE: it has been identified as {_detect_reply_language(query)}. "
        "Your entire reply MUST be written in exactly that language/script, no exceptions — this is "
        "a confirmed classification, not a guess, so do not second-guess or override it."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + language_directive},
        {"role": "user", "content": query},
    ]

    try:
        assistant_message = _chat(messages, tools=[SEARCH_PRODUCTS_TOOL])
    except AssistantUnavailableError:
        logger.warning("Ollama unavailable; falling back to direct search for query=%r", query)
        return _direct_search_fallback(
            query, "Our AI assistant is temporarily unavailable, but here's what matched your search directly."
        )

    tool_calls = assistant_message.get("tool_calls") or []
    raw_args = None
    if tool_calls:
        raw_args = tool_calls[0].get("function", {}).get("arguments")
    else:
        # Either the model answered without looking anything up, or (seen in practice with
        # this quantized model) it wrote the tool call out as raw JSON text instead of using
        # Ollama's structured tool_calls field. Try to recover the latter before falling
        # back to "never trust unlooked-up text" grounding on the raw query.
        raw_args = _extract_inline_tool_call(assistant_message.get("content"))

    if raw_args is None and not tool_calls:
        search_result, products = _run_search_tool({"query": query})
        return {
            "message": assistant_message.get("content") or "Here's what I found for you.",
            "products": products,
            "applied_filters": search_result["applied_filters"],
            "ai_generated": True,
        }

    tool_args = _sanitize_tool_args(raw_args)
    tool_args.setdefault("query", query)
    search_result, products = _run_search_tool(tool_args)

    # Replay a clean version of the tool-call turn rather than the model's own message —
    # when it was recovered from garbled inline text, echoing that same garbled text back
    # in would just invite the model to repeat the mistake on the next turn.
    messages.append(
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "search_products", "arguments": tool_args}}]}
    )
    messages.append(
        {
            "role": "tool",
            "content": json.dumps({"count": search_result["count"], "products": products}),
        }
    )

    try:
        final_message = _chat(messages)
        reply_text = final_message.get("content") or ""
    except AssistantUnavailableError:
        reply_text = ""

    # Guard against the same "wrote a tool call as text instead of a real answer" failure
    # mode happening again on this second round-trip — don't show that raw JSON to the user.
    if _extract_inline_tool_call(reply_text) is not None:
        reply_text = ""

    if not reply_text.strip():
        reply_text = (
            f"Found {len(products)} matching product(s)." if products
            else "No matching products found — try broadening your search."
        )

    return {
        "message": reply_text,
        "products": products,
        "applied_filters": search_result["applied_filters"],
        "ai_generated": True,
    }

"""Settings for running the test suite (`manage.py test --settings=FaizanMart.settings.test`).

Uses a dummy cache so DRF rate-limiting (which stores counters in the cache) doesn't leak
state between the 100+ test methods that share one Redis connection across a single test
run — every request would otherwise eventually start seeing 429s that have nothing to do
with what that particular test is checking. Tests that actually verify throttling behavior
override CACHES back to a real (local-memory) backend for just that test class.
"""

from .dev import *  # noqa: F401,F403

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Same reasoning as CACHES above: an in-memory channel layer per test process instead of a
# shared real Redis connection, so chat tests don't need a live Redis and don't leak state.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Same reasoning again, one level worse: Elasticsearch isn't tied to Postgres's per-test
# transaction at all, so a Product created (and rolled back) by any of the ~180 other tests
# across the suite would otherwise leave a permanent, never-cleaned-up document in the real
# "products" index — signals fire on save() regardless of whether the transaction that save()
# happened in ever commits. Auto-indexing is off by default in tests; the search tests index
# explicitly via `ProductDocument().update(instance)`, which isn't gated by this flag.
ELASTICSEARCH_DSL_AUTOSYNC = False

# Celery tasks (email sending, cleanup, invoice emails) run synchronously in-process during
# tests instead of being enqueued to a real broker — otherwise .delay() calls would silently
# no-op (no worker consuming them in the test process) and things like `mail.outbox`
# assertions on registration/password-reset would break.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Points at a port nothing listens on, so any assistant test that forgets to mock
# apps.assistant.services._chat fails fast with a connection error instead of silently
# hitting a real local Ollama instance (which may or may not be running on the dev
# machine) and making the test's outcome depend on machine state.
OLLAMA_URL = "http://localhost:1"

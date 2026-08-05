"""
Shared Django settings for FaizanMart, common to every environment.
Environment-specific overrides live in dev.py / prod.py.
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])


# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "csp",
    "django_elasticsearch_dsl",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.vendors",
    "apps.catalog",
    "apps.inventory",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.shipping",
    "apps.coupons",
    "apps.reviews",
    "apps.support",
    "apps.notifications",
    "apps.analytics",
    "apps.sitesettings",
    "apps.marketing",
    "apps.chat",
    "apps.assistant",
    "apps.storefront",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

if env("CLOUDINARY_URL", default=""):
    INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CurrentRequestMiddleware",
]

ROOT_URLCONF = "FaizanMart.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.storefront.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "FaizanMart.wsgi.application"
ASGI_APPLICATION = "FaizanMart.asgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": env.db("DATABASE_URL"),
}


# Cache / Redis

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


# Elasticsearch (product search)

ELASTICSEARCH_URL = env("ELASTICSEARCH_URL", default="http://localhost:9200")
ELASTICSEARCH_DSL = {
    "default": {"hosts": ELASTICSEARCH_URL},
}


# Channels (real-time chat WebSocket layer)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}


# Celery

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-sessions": {
        "task": "apps.accounts.tasks.cleanup_expired_sessions_task",
        "schedule": crontab(hour=3, minute=0),  # daily at 03:00 UTC
    },
    "cleanup-stale-guest-carts": {
        "task": "apps.cart.tasks.cleanup_stale_guest_carts_task",
        "schedule": crontab(hour=3, minute=30),  # daily at 03:30 UTC
    },
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static & media files

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    # Falls back to the local filesystem (Django's own built-in default) whenever
    # CLOUDINARY_URL isn't set — e.g. CI — so that ANY ImageField/FileField `.url` access
    # (template <img>, DRF serializer field, etc.) has a working storage backend instead of
    # raising InvalidStorageError. Without this key at all, Django has no "default" entry
    # in STORAGES and blows up the first time anything touches a file field's .url.
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

if env("CLOUDINARY_URL", default=""):
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

# Logging — plain console output (no file handler) so it lands on stdout, where Docker/
# journald/whatever's supervising the process already collects and rotates it for us.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "accounts:login"


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Lets the server-rendered storefront (apps.storefront) call these same API
        # endpoints via fetch() using the normal Django session cookie + CSRF token,
        # instead of juggling a separate JWT for same-origin browser requests.
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticatedOrReadOnly",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Global safety net for every API endpoint.
        "anon": "60/min",
        "user": "300/min",
        # Tighter, endpoint-specific scopes (set via `throttle_scope`) for
        # brute-force-sensitive and money-moving endpoints.
        "auth_login": "5/min",
        "auth_register": "5/min",
        "password_reset": "5/min",
        "otp": "5/min",
        "checkout": "10/min",
        "payment": "10/min",
        # LLM calls are slow and comparatively expensive to run, so this gets its own,
        # tighter scope rather than sharing the general "user"/"anon" default.
        "assistant": "15/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FaizanMart API",
    "DESCRIPTION": "Enterprise multi-vendor e-commerce platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


# CORS

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

from corsheaders.defaults import default_headers  # noqa: E402

# X-Cart-Token carries the guest cart identifier (apps/cart/services.py) — not part of the
# default cors-headers allowlist, so cross-origin browser clients need it added explicitly.
CORS_ALLOW_HEADERS = [*default_headers, "x-cart-token"]


# Security headers
# HTTPS redirect + HSTS + secure cookies are environment-sensitive (would break local HTTP
# development) so those live in prod.py; everything here is safe to always enforce.

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Content-Security-Policy (django-csp). "unsafe-inline" on style-src is needed by the Django
# admin, DRF's browsable API, and the Swagger UI docs page; script-src stays locked to 'self'
# plus the specific CDN Swagger UI's assets load from (drf-spectacular's SpectacularSwaggerView).
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "https://res.cloudinary.com"],
        "script-src": ["'self'", "https://cdn.jsdelivr.net"],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
        "connect-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
}


# Email

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_HOST_NAME = env("EMAIL_HOST_NAME", default="FaizanMart")
DEFAULT_FROM_EMAIL = f"{EMAIL_HOST_NAME} <{EMAIL_HOST_USER}>"


# Google OAuth (ID-token verification; blank until credentials exist)

GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")


# Stripe (blank until credentials exist; payments/services/stripe.py fails loudly if used unconfigured)

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_CURRENCY = env("STRIPE_CURRENCY", default="usd")


# JazzCash (Mobile Wallet / Page-Post hosted checkout; blank until credentials exist)

JAZZCASH_MERCHANT_ID = env("JAZZCASH_MERCHANT_ID", default="")
JAZZCASH_PASSWORD = env("JAZZCASH_PASSWORD", default="")
JAZZCASH_INTEGRITY_SALT = env("JAZZCASH_INTEGRITY_SALT", default="")
JAZZCASH_RETURN_URL = env("JAZZCASH_RETURN_URL", default="")
JAZZCASH_ENVIRONMENT = env("JAZZCASH_ENVIRONMENT", default="sandbox")


# EasyPaisa (hosted checkout redirect; blank until credentials exist)

EASYPAISA_STORE_ID = env("EASYPAISA_STORE_ID", default="")
EASYPAISA_HASH_KEY = env("EASYPAISA_HASH_KEY", default="")
EASYPAISA_RETURN_URL = env("EASYPAISA_RETURN_URL", default="")
EASYPAISA_ENVIRONMENT = env("EASYPAISA_ENVIRONMENT", default="sandbox")


# AI shopping assistant (apps.assistant) — local, free inference via Ollama instead of a
# paid API. Defaults assume `ollama serve` running on the same host with the model pulled
# (`ollama pull qwen2.5:7b`); override OLLAMA_URL for a remote/containerized Ollama.
OLLAMA_URL = env("OLLAMA_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="qwen2.5:7b")
OLLAMA_TIMEOUT_SECONDS = env.int("OLLAMA_TIMEOUT_SECONDS", default=120)

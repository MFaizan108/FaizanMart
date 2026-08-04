from .base import *  # noqa: F401,F403

DEBUG = False

# HTTPS + HSTS — only enforced here since they'd break local HTTP development in dev.py.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Cookies only travel over HTTPS and never touch client-side JS (HttpOnly is already the
# default from base.py; repeated here so prod's cookie posture reads as complete on its own).
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

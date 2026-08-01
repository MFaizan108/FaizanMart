from .base import *  # noqa: F401,F403

DEBUG = True

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

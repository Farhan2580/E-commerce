"""Loopback-only development server configuration; never used by WSGI/ASGI."""
from .settings import *  # noqa: F403

ROOT_URLCONF = 'djangoProject13.development_urls'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

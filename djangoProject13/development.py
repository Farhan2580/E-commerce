"""Loopback-only development server configuration; never used by WSGI/ASGI."""
from .settings import *  # noqa: F403

ROOT_URLCONF = 'djangoProject13.development_urls'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# runserver's static handler is disabled when DEBUG=False. Serve source assets
# through the existing WhiteNoise middleware locally, without collectstatic.
# Refresh on each request so CSS/JS edits appear immediately. WSGI/ASGI continue
# to use settings.py and collected assets; these flags are development-only.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

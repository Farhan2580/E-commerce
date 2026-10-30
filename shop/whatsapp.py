"""Resolve only explicitly configured WhatsApp destinations, never store.phone."""
import re
from urllib.parse import parse_qs, urlencode, urlsplit

DEFAULT_MESSAGE = 'Hello GadgetFlow, I need help with a product.'


def whatsapp_url(value):
    parts = urlsplit(value)
    host = (parts.hostname or '').removeprefix('www.')
    query = parse_qs(parts.query)
    if parts.scheme != 'https' or parts.username or parts.password or parts.port:
        return None
    if host == 'wa.me':
        phone = parts.path.strip('/')
    elif host in {'api.whatsapp.com', 'web.whatsapp.com'} and parts.path == '/send':
        phone = query.get('phone', [''])[0]
    else:
        return None
    # E.164 international digits; no guessed country code or contact fallback.
    if not re.fullmatch(r'[1-9][0-9]{6,14}', phone):
        return None
    message = query.get('text', [DEFAULT_MESSAGE])[0]
    return 'https://wa.me/' + phone + '?' + urlencode({'text': message})

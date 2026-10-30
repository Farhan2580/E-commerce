"""Read-only HTTP image audit. Usage: python tools/verify_media_http.py ORIGIN"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from io import BytesIO
import json
import sys
from urllib.parse import urljoin
from urllib.request import urlopen
from urllib.error import HTTPError
from PIL import Image


class Sources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('src'):
            self.images.append(attrs['src'])


def inspect(url):
    try:
        with urlopen(url, timeout=30) as response:
            body = response.read(25 * 1024 * 1024)
            image = Image.open(BytesIO(body))
            image.verify()
            return {'url': url, 'status': response.status, 'valid': True, 'type': response.headers.get('Content-Type')}
    except HTTPError as exc:
        return {'url': url, 'status': exc.code, 'valid': False}
    except Exception as exc:
        return {'url': url, 'valid': False, 'error': type(exc).__name__}


if __name__ == '__main__':
    origin = sys.argv[1].rstrip('/')
    pages = {}
    for path in ['/', '/products/', '/product/1/']:
        parser = Sources()
        with urlopen(origin + path, timeout=60) as response:
            parser.feed(response.read().decode())
        pages[path] = list(dict.fromkeys(urljoin(origin + path, src) for src in parser.images))
    urls = list(dict.fromkeys(url for values in pages.values() for url in values))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(inspect, urls))
    print(json.dumps({'pages': pages, 'images': results}, indent=2))
    sys.exit(1 if not urls or any(not r['valid'] for r in results) else 0)

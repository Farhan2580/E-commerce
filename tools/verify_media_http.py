"""Read-only HTTP image audit. Usage: python tools/verify_media_http.py ORIGIN"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from io import BytesIO
import json
import argparse
import sys
from urllib.parse import urljoin
from urllib.request import urlopen
from urllib.error import HTTPError
from PIL import Image

EXACT_MEDIA_PATHS = [
    '/media/products/gallery-7.jpg',
    '/media/product_images/asus.webp',
    '/media/offers/Macbook-Offer-Banner-5750.jpg',
]


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
            valid = response.status == 200 and response.headers.get('Content-Type', '').startswith('image/')
            return {'url': url, 'status': response.status, 'valid': valid, 'type': response.headers.get('Content-Type')}
    except HTTPError as exc:
        return {'url': url, 'status': exc.code, 'type': exc.headers.get('Content-Type'), 'valid': False}
    except Exception as exc:
        return {'url': url, 'valid': False, 'error': type(exc).__name__}


if __name__ == '__main__':
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('origin')
    arguments.add_argument('--extra-url', action='append', default=[],
                           help='Include the actual newly uploaded category URL; repeat for other uploads.')
    args = arguments.parse_args()
    origin = args.origin.rstrip('/')
    pages = {}
    for path in ['/', '/products/', '/product/1/', '/offers/']:
        parser = Sources()
        with urlopen(origin + path, timeout=60) as response:
            parser.feed(response.read().decode())
        pages[path] = list(dict.fromkeys(urljoin(origin + path, src) for src in parser.images))
    pages['exact_legacy_paths'] = [origin + path for path in EXACT_MEDIA_PATHS]
    pages['additional_uploads'] = [urljoin(origin + '/', url) for url in args.extra_url]
    urls = list(dict.fromkeys(url for values in pages.values() for url in values))
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(inspect, urls))
    print(json.dumps({'pages': pages, 'images': results}, indent=2))
    sys.exit(1 if not urls or any(not r['valid'] for r in results) else 0)

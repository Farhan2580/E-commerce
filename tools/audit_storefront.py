"""Read-only public page/asset audit; no orders, cart writes or payment calls."""
import argparse
from html import unescape
from html.parser import HTMLParser
import json
import hashlib
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.urls.append(attrs['href'])
        if tag == 'script' and attrs.get('src'):
            self.urls.append(attrs['src'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    args = parser.parse_args()
    origin = args.origin.rstrip('/')
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    report = {'origin': origin, 'pages': [], 'assets': [], 'catalog_names': []}
    paths = ['/', '/products/', '/offers/', '/cart/', '/checkout/']
    assets = set()
    for path in paths:
        try:
            with opener.open(origin + path, timeout=60) as response:
                body = response.read().decode()
                report['pages'].append({'path': path, 'status': response.status,
                                        'final_path': urlsplit(response.url).path,
                                        'html': response.headers.get('Content-Type', '').startswith('text/html')})
            if path == '/products/':
                report['catalog_names'] = sorted(set(unescape(name) for name in re.findall(r'aria-label="View ([^"]+)"', body)))
                product_ids = re.findall(r'data-product-id="(\d+)"', body)
                if product_ids:
                    paths.append('/product/' + product_ids[0] + '/')
            if path == '/':
                categories = re.findall(r'href="(/products/\?category=\d+)"', body)
                if categories:
                    paths.append(unescape(categories[0]))
            parsed = Assets()
            parsed.feed(body)
            assets.update(urljoin(origin + path, url) for url in parsed.urls if urlsplit(urljoin(origin, url)).netloc == urlsplit(origin).netloc)
        except HTTPError as exc:
            report['pages'].append({'path': path, 'status': exc.code})
    for url in sorted(assets):
        try:
            with opener.open(url, timeout=30) as response:
                content = response.read()
                report['assets'].append({'path': urlsplit(url).path, 'status': response.status,
                                         'content_type': response.headers.get('Content-Type'),
                                         'sha256': hashlib.sha256(content).hexdigest(),
                                         'normalized_sha256': hashlib.sha256(content.removeprefix(b'\xef\xbb\xbf').replace(b'\r\n', b'\n')).hexdigest()})
        except HTTPError as exc:
            report['assets'].append({'path': urlsplit(url).path, 'status': exc.code})
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if all(row['status'] == 200 for row in report['pages'] + report['assets']) else 1)

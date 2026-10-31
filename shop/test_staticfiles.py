"""Exercise the same collected-asset path used with public debug pages disabled."""
from html.parser import HTMLParser
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, override_settings


class StylesheetLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.paths.append(attrs['href'])


class CollectedStaticTests(SimpleTestCase):
    @override_settings(DEBUG=False, WHITENOISE_USE_FINDERS=True, WHITENOISE_AUTOREFRESH=True)
    def test_local_css_and_js_without_collected_assets(self):
        with TemporaryDirectory() as directory, self.settings(STATIC_ROOT=directory):
            client = Client()
            for name in ('store-components', 'premium', 'footer', 'commerce', 'mobile'):
                for extension in ('css', 'js'):
                    with self.subTest(name=name, extension=extension):
                        response = client.get(f'/static/shop/{name}.{extension}')
                        self.assertEqual(response.status_code, 200)
                        content_type = response['Content-Type'].split(';')[0]
                        if extension == 'css':
                            self.assertEqual(content_type, 'text/css')
                        else:
                            self.assertIn(content_type, ('text/javascript', 'application/javascript'))
                        body = b''.join(response.streaming_content)
                        self.assertTrue(body)
                        self.assertNotIn(b'<!doctype html', body.lower())
                        response.close()

    @override_settings(DEBUG=False, WHITENOISE_USE_FINDERS=False, WHITENOISE_AUTOREFRESH=False)
    def test_actual_storefront_stylesheets_are_css_with_debug_off(self):
        with TemporaryDirectory() as directory, self.settings(STATIC_ROOT=directory):
            call_command('collectstatic', interactive=False, verbosity=0)
            links = StylesheetLinks()
            links.feed(render_to_string('shop/includes/store_assets.html'))
            self.assertEqual(len(links.paths), 4)
            client = Client()
            for path in links.paths:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response['Content-Type'].split(';')[0], 'text/css')
                    body = b''.join(response.streaming_content)
                    self.assertIn(b'.gf-', body)
                    self.assertNotIn(b'<!doctype html', body.lower())
                    response.close()

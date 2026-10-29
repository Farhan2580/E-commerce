"""Real upload bytes through Admin, storage, rendered templates and media HTTP."""
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse, resolve, Resolver404
from .models import Category, Product, Banner


class ImageSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('src', '').startswith('/media/'):
            self.sources.append(attrs['src'])


@override_settings(ROOT_URLCONF='djangoProject13.development_urls', DEBUG=False)
class LocalMediaTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.media_settings = override_settings(MEDIA_ROOT=self.directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        # Existing, real project images. Never touch their storage or source records.
        self.jpeg = (Path(settings.BASE_DIR) / 'media/products/gallery-7.jpg').read_bytes()
        self.png = (Path(settings.BASE_DIR) / 'media/products/Apple-iPhone-16-Pro-Max.png').read_bytes()
        self.category = Category.objects.create(name='Temporary image category', featured=True)
        self.category.image.save('real-category.jpg', SimpleUploadedFile('real-category.jpg', self.jpeg, 'image/jpeg'))
        self.product = Product.objects.create(name='Temporary image product', category=self.category, price=100, stock=5)
        self.product.image.save('real-product.jpg', SimpleUploadedFile('real-product.jpg', self.jpeg, 'image/jpeg'))
        self.banner = Banner.objects.create(title='Temporary uploaded banner', position=0)
        self.banner.image.save('real-banner.jpg', SimpleUploadedFile('real-banner.jpg', self.jpeg, 'image/jpeg'))

    def assert_image(self, url, expected=None):
        response = self.client.get(url, HTTP_HOST='localhost', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(response.status_code, 200, url)
        self.assertTrue(response['Content-Type'].startswith('image/'), response['Content-Type'])
        body = b''.join(response.streaming_content)
        response.close()
        Image.open(BytesIO(body)).verify()
        if expected is not None:
            self.assertEqual(body, expected)

    def test_categories_cards_details_and_uploaded_banners_render_real_media(self):
        home = self.client.get(reverse('home'), HTTP_HOST='localhost')
        self.assertContains(home, self.category.image.url)
        self.assertContains(home, self.banner.image.url)
        catalog = self.client.get(reverse('product_list'), HTTP_HOST='localhost')
        detail = self.client.get(reverse('product_detail', args=[self.product.pk]), HTTP_HOST='localhost')
        self.assertContains(catalog, self.product.image.url)
        self.assertContains(detail, self.product.image.url)
        # Existing source DB fixtures may refer to other MEDIA_ROOT paths. Verify
        # the actual temporary uploaded targets rather than fabricate replacements.
        for url in [self.category.image.url, self.product.image.url, self.banner.image.url]:
            self.assert_image(url, self.jpeg)

    def test_admin_image_update_changes_url_and_preserves_previous_file(self):
        admin = User.objects.create_superuser('media-test-admin', 'media@example.test', 'test-only-password')
        self.client.force_login(admin)
        original_path = Path(self.product.image.path)
        original_url = self.product.image.url
        response = self.client.post(reverse('admin:shop_product_change', args=[self.product.pk]), {
            'name': self.product.name, 'category': self.category.pk, 'price': '100.00',
            'stock': '5', 'position': '0', 'specifications': '{}',
            'image': SimpleUploadedFile('real-admin-update.png', self.png, content_type='image/png'),
            'variants-TOTAL_FORMS': '0', 'variants-INITIAL_FORMS': '0',
            'gallery-TOTAL_FORMS': '0', 'gallery-INITIAL_FORMS': '0',
            'warranty-TOTAL_FORMS': '0', 'warranty-INITIAL_FORMS': '0', '_save': 'Save',
        }, HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 302, response.content.decode()[:1200])
        self.product.refresh_from_db()
        self.assertNotEqual(self.product.image.url, original_url)
        self.assertTrue(original_path.exists())
        self.assertEqual(original_path.read_bytes(), self.jpeg)
        self.assert_image(self.product.image.url, self.png)
        detail = self.client.get(reverse('product_detail', args=[self.product.pk]), HTTP_HOST='localhost')
        self.assertContains(detail, self.product.image.url)

    def test_media_is_loopback_only_and_never_serves_parent_paths(self):
        response = self.client.get(self.product.image.url, HTTP_HOST='localhost', REMOTE_ADDR='192.0.2.50')
        self.assertEqual(response.status_code, 404)
        self.assertIn(self.client.get('/media/../db.sqlite3', HTTP_HOST='localhost').status_code, [400, 404])
        self.assertEqual(self.client.get('/media/', HTTP_HOST='localhost').status_code, 404)

    @override_settings(ROOT_URLCONF='djangoProject13.urls', DEBUG=False)
    def test_production_configuration_does_not_serve_uploads(self):
        with self.assertRaises(Resolver404):
            resolve(self.product.image.url)
        self.assertEqual(self.client.get(self.product.image.url).status_code, 404)

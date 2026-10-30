import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from cloudinary.exceptions import NotFound
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from .cloudinary_storage import CloudinaryMediaStorage
from .models import Category, Product, Banner, Offer


OPTIONS = {'cloud_name': 'fixture-cloud', 'api_key': 'fixture', 'api_secret': 'fixture'}
CLOUDINARY_STORAGES = {
    'default': {'BACKEND': 'shop.cloudinary_storage.CloudinaryMediaStorage', 'OPTIONS': OPTIONS},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}


@override_settings(MEDIA_STORAGE='cloudinary', STORAGES=CLOUDINARY_STORAGES)
class CloudinaryMediaTests(TestCase):
    def setUp(self):
        self.original = (settings.BASE_DIR / 'media/products/gallery-7.jpg').read_bytes()
        self.assets = {}
        self.storage = CloudinaryMediaStorage(**OPTIONS)
        self.upload = patch('cloudinary.uploader.upload', side_effect=self.upload_asset).start()
        patch('cloudinary.api.resource', side_effect=self.resource).start()
        patch('shop.cloudinary_storage.urlopen', side_effect=self.download).start()
        self.addCleanup(patch.stopall)
        self.category = Category.objects.create(name='Cloudinary category', image='categories/original.jpg')
        self.product = Product.objects.create(name='Cloudinary product', category=self.category,
                                              price=100, stock=2, image='products/original.jpg')

    def upload_asset(self, content, **options):
        self.assertIs(options['overwrite'], False)
        key = options['public_id']
        existing = key in self.assets
        if not existing:
            self.assets[key] = content.read()
        return {'public_id': key, 'version': 123, 'existing': existing}

    def resource(self, public_id, **options):
        if public_id not in self.assets:
            raise NotFound('fixture missing')
        return {'public_id': public_id, 'bytes': len(self.assets[public_id])}

    def download(self, url, **kwargs):
        path = urlsplit(url).path.split('/upload/', 1)[1]
        if path.split('/')[0].startswith('v'):
            path = path.split('/', 1)[1]
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {'Content-Type': 'image/jpeg'}
        response.read.side_effect = BytesIO(self.assets[path]).read
        return response

    def test_mapping_preserves_exact_keys_and_distinguishes_extensions(self):
        name = 'categories/Original image.jpg'
        expected = 'gadgetflow/media/' + hashlib.sha256(name.encode()).hexdigest()
        self.assertEqual(self.storage.public_id(name), expected)
        self.assertNotEqual(self.storage.public_id('products/item.jpg'), self.storage.public_id('products/item.png'))
        self.assertEqual(self.storage.url(name), CloudinaryMediaStorage(**OPTIONS).url(name))
        self.assertTrue(self.storage.url(name).startswith('https://res.cloudinary.com/fixture-cloud/image/upload/'))
        self.assertNotIn('api_secret', self.storage.url(name))
        for key in ['../private.jpg', '/absolute.jpg', 'folder\\image.jpg']:
            with self.assertRaises(ValueError):
                self.storage.public_id(key)

    def test_new_uploads_do_not_replace_originals(self):
        first = self.storage.save('categories/new.jpg', ContentFile(self.original))
        second = self.storage.save('categories/new.jpg', ContentFile(self.original))
        self.assertNotEqual(first, second)
        with self.storage.open(first) as handle:
            self.assertEqual(handle.read(), self.original)
        self.assertEqual(self.storage.size(first), len(self.original))

    def test_transfer_upload_skip_conflict_and_database_preservation(self):
        with TemporaryDirectory() as directory:
            for name in [self.category.image.name, self.product.image.name]:
                destination = Path(directory) / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(self.original)
            output = StringIO()
            call_command('transfer_media', source=directory, stdout=output)
            self.upload.assert_not_called()
            self.assertIn('public_id', json.loads(output.getvalue())['references'][0])
            for status in ['uploaded', 'existing_identical']:
                output = StringIO()
                call_command('transfer_media', source=directory, upload=True, stdout=output)
                self.assertTrue(all(row['status'] == status for row in json.loads(output.getvalue())['references']))
            key = self.storage.public_id(self.category.image.name)
            self.assets[key] = b'existing unrelated bytes'
            with self.assertRaises(CommandError):
                call_command('transfer_media', source=directory, upload=True, stdout=StringIO())
            self.assertEqual(self.assets[key], b'existing unrelated bytes')
        self.category.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.category.image.name, 'categories/original.jpg')
        self.assertEqual(self.product.image.name, 'products/original.jpg')

    def test_all_existing_imagefields_render_cloudinary_urls_without_data_changes(self):
        banner = Banner.objects.create(title='Original banner', image='banners/original.jpg', link='/products/')
        offer = Offer.objects.create(title='Original offer', image='offers/original.jpg', is_active=True)
        home = self.client.get(reverse('home'))
        for image in [self.category.image, banner.image]:
            self.assertContains(home, image.url)
        self.assertContains(self.client.get(reverse('product_list')), self.product.image.url)
        self.assertContains(self.client.get(reverse('product_detail', args=[self.product.pk])), self.product.image.url)
        self.assertContains(self.client.get(reverse('offers')), offer.image.url)
        # Reconstructing storage, as a new process after redeploy would do, keeps URLs stable.
        self.assertEqual(self.category.image.url, CloudinaryMediaStorage(**OPTIONS).url(self.category.image.name))

    def test_category_admin_upload_and_legacy_url(self):
        admin = User.objects.create_superuser('cloudinary-admin', 'cloudinary@example.test', 'test-password')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:shop_category_change', args=[self.category.pk]), {
            'name': self.category.name, 'featured': 'on', 'position': '0', 'parent': '',
            'image': SimpleUploadedFile('new-admin.jpg', self.original, 'image/jpeg'), '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        self.assertTrue(self.category.image.name.startswith('categories/new-admin'))
        self.assertContains(self.client.get(reverse('home')), self.category.image.url)
        with self.category.image.open('rb') as original:
            self.assertEqual(original.read(), self.original)
        from .media_redirect import media_redirect
        from django.test import RequestFactory
        redirect = media_redirect(RequestFactory().get('/media/' + self.category.image.name), self.category.image.name)
        self.assertEqual(redirect.status_code, 302)
        self.assertEqual(redirect.url, self.category.image.url)

    def test_manifest_transfers_production_only_reference_without_database_queries(self):
        with TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'categories').mkdir()
            (source / 'categories/production-only.jpg').write_bytes(self.original)
            manifest = source / 'manifest.json'
            manifest.write_text(json.dumps({'images': [{'key': 'categories/production-only.jpg'}]}))
            output = StringIO()
            with self.assertNumQueries(0):
                call_command('transfer_media', source=directory, manifest=str(manifest), upload=True, stdout=output)
            row = json.loads(output.getvalue())['references'][0]
            self.assertEqual(row['status'], 'uploaded')
            self.assertFalse(Category.objects.filter(pk=98765).exists())

    def test_invalid_manifest_key_and_missing_original_make_no_upload(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / 'manifest.json'
            for name in ['../private.jpg', 'categories/missing.jpg']:
                manifest.write_text(json.dumps({'images': [{'model': 'Category', 'pk': 1,
                    'field': 'image', 'key': name}]}))
                with self.assertRaises((CommandError, ValueError)):
                    call_command('transfer_media', source=directory, manifest=str(manifest), upload=True, stdout=StringIO())
            self.upload.assert_not_called()

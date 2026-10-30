from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from urllib.request import Request
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Product, Banner
from tools.recover_media import NoRedirect, save_original


TOKEN = 'fixture_recovery_' + 'x' * 48


@override_settings(DEBUG=False, MEDIA_RECOVERY_ENABLED=True, MEDIA_RECOVERY_TOKEN=TOKEN)
class MediaRecoveryTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.override = override_settings(MEDIA_ROOT=self.root,
            MEDIA_RECOVERY_EXPIRES_AT=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.original = (settings.BASE_DIR / 'media/products/gallery-7.jpg').read_bytes()
        (self.root / 'categories').mkdir()
        (self.root / 'categories/production-only.jpg').write_bytes(self.original)
        self.category = Category.objects.create(name='Private category name', image='categories/production-only.jpg')
        self.product = Product.objects.create(name='Private product record', category=self.category,
                                              price=5, stock=2, image='products/missing.jpg')
        self.url = reverse('media_recovery_manifest')

    def get(self, url=None, **kwargs):
        return self.client.get(url or self.url, secure=True, HTTP_AUTHORIZATION='Bearer ' + TOKEN, **kwargs)

    def test_no_auth_query_tokens_disabled_expired_and_http_reveal_nothing(self):
        with self.assertNumQueries(0):
            self.assertEqual(self.client.get(self.url, secure=True).status_code, 404)
            self.assertEqual(self.client.get(self.url, {'token': TOKEN}, secure=True).status_code, 404)
            self.assertEqual(self.client.get(self.url, secure=True, HTTP_AUTHORIZATION='Bearer wrong').status_code, 404)
            self.assertEqual(self.client.get(self.url, HTTP_AUTHORIZATION='Bearer ' + TOKEN).status_code, 404)
        options = [
            {'MEDIA_RECOVERY_ENABLED': False}, {'MEDIA_RECOVERY_TOKEN': 'short'}, {'DEBUG': True},
            {'MEDIA_RECOVERY_EXPIRES_AT': 'invalid'},
            {'MEDIA_RECOVERY_EXPIRES_AT': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()},
            {'MEDIA_RECOVERY_EXPIRES_AT': (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()},
        ]
        for option in options:
            with self.subTest(option=option), override_settings(**option), self.assertNumQueries(0):
                response = self.get()
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, b'')
                self.assertIn('no-store', response['Cache-Control'])

    def test_manifest_is_minimal_private_and_does_not_change_records(self):
        before = (self.category.image.name, self.product.image.name)
        response = self.get()
        self.assertEqual(response.status_code, 200)
        rows = response.json()['images']
        self.assertEqual(set(row['key'] for row in rows), set(before))
        ready = next(row for row in rows if row['status'] == 'ready')
        self.assertEqual(ready['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(next(row for row in rows if row['key'] == before[1])['status'], 'missing')
        for forbidden in [TOKEN, self.category.name, self.product.name, str(self.root), 'api_secret', 'filesystem_path', 'pk', 'model']:
            self.assertNotIn(forbidden, response.content.decode())
        self.assertIn('Authorization', response['Vary'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('noindex', response['X-Robots-Tag'])
        self.assertNotIn('Access-Control-Allow-Origin', response)
        self.category.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.category.image.name, self.product.image.name), before)
        self.assertEqual((self.root / before[0]).read_bytes(), self.original)

    def test_authenticated_download_is_exact_and_restricted_to_known_keys(self):
        row = next(row for row in self.get().json()['images'] if row['status'] == 'ready')
        url = reverse('media_recovery_original', args=[row['download_id']])
        with self.assertNumQueries(0):
            self.assertEqual(self.client.get(url, secure=True).status_code, 404)
        response = self.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))
        self.assertEqual(b''.join(response.streaming_content), self.original)
        self.assertEqual(response['X-Media-SHA256'], row['sha256'])
        self.assertEqual(self.get(reverse('media_recovery_original', args=['a' * 64])).status_code, 404)
        self.assertEqual(self.get(url + '?source=configured').status_code, 404)
        self.assertEqual(self.get(reverse('media_recovery_original', args=['not-a-digest'])).status_code, 404)

    def test_only_get_and_pagination_limits(self):
        for method in ['post', 'put', 'delete', 'patch', 'head']:
            with self.subTest(method=method), self.assertNumQueries(0):
                response = getattr(self.client, method)(self.url, secure=True, HTTP_AUTHORIZATION='Bearer ' + TOKEN)
                self.assertEqual(response.status_code, 405)
        with patch('shop.media_recovery.PAGE_SIZE', 1):
            page = self.get().json()
            self.assertEqual(len(page['images']), 1)
            self.assertEqual(page['next_offset'], 1)
        self.assertEqual(self.get(self.url + '?offset=-1').status_code, 400)
        self.assertEqual(self.get(self.url + '?source=arbitrary').status_code, 400)

    def test_unsafe_invalid_and_too_large_files_are_not_downloadable(self):
        Banner.objects.create(title='Unsafe', image='../private.jpg')
        (self.root / 'categories/not-image.jpg').write_bytes(b'not an image')
        Category.objects.create(name='Invalid original', image='categories/not-image.jpg')
        rows = self.get().json()['images']
        self.assertEqual(next(row for row in rows if row['key'] == '../private.jpg')['status'], 'unsafe_key')
        self.assertEqual(next(row for row in rows if row['key'] == 'categories/not-image.jpg')['status'], 'unreadable')
        with patch('shop.media_recovery.MAX_BYTES', 1):
            rows = self.get().json()['images']
            self.assertEqual(next(row for row in rows if row['key'] == self.category.image.name)['status'], 'too_large')

    def test_configured_storage_is_read_only_and_does_not_return_provider_urls(self):
        storage = MagicMock()
        storage.exists.return_value = True
        storage.open.side_effect = lambda *args: ContentFile(self.original)
        with patch('shop.media_recovery.default_storage', storage):
            response = self.get(self.url + '?source=configured')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(row['status'] == 'ready' for row in response.json()['images']))
            storage.save.assert_not_called()
            storage.delete.assert_not_called()
            storage.url.assert_not_called()

    def test_backup_client_never_overwrites_and_refuses_redirects(self):
        row = {'key': 'categories/production-only.jpg', 'bytes': len(self.original),
               'sha256': hashlib.sha256(self.original).hexdigest()}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(save_original(root, row, self.original), 'saved_verified')
            self.assertEqual(save_original(root, row, self.original), 'existing_identical')
            (root / row['key']).write_bytes(b'existing different bytes')
            self.assertEqual(save_original(root, row, self.original), 'conflict_not_overwritten')
            self.assertEqual((root / row['key']).read_bytes(), b'existing different bytes')
            with self.assertRaises(ValueError):
                save_original(root, {**row, 'key': '../private.jpg'}, self.original)
        with self.assertRaises(RuntimeError):
            NoRedirect().redirect_request(Request('https://example.test'), None, 302, '', {}, 'https://elsewhere.test')

    def test_operator_client_exports_minimal_manifest_and_verified_survivors(self):
        from tools.recover_media import main

        def open_request(request, **kwargs):
            parsed = urlsplit(request.full_url)
            path = parsed.path + ('?' + parsed.query if parsed.query else '')
            response = self.client.get(path, secure=True,
                HTTP_AUTHORIZATION=request.get_header('Authorization'))
            body = b''.join(response.streaming_content) if response.streaming else response.content
            response.close()
            fake = MagicMock()
            fake.status = response.status_code
            fake.__enter__.return_value = fake
            fake.read.side_effect = BytesIO(body).read
            return fake

        opener = MagicMock()
        opener.open.side_effect = open_request
        with TemporaryDirectory() as directory:
            arguments = ['recover_media.py', '--origin', 'https://example.test',
                         '--destination', directory, '--download']
            with patch('sys.argv', arguments), patch('sys.stdin.isatty', return_value=True), \
                    patch('tools.recover_media.getpass.getpass', return_value=TOKEN), \
                    patch('tools.recover_media.build_opener', return_value=opener), \
                    patch('builtins.print'):
                # The missing production original is accurately reported, not hidden.
                self.assertEqual(main(), 1)
            manifest = (Path(directory) / 'manifest.json').read_text()
            report = (Path(directory) / 'backup-report.json').read_text()
            for forbidden in [TOKEN, 'download_id', 'Authorization', 'model', 'pk']:
                self.assertNotIn(forbidden, manifest + report)
            self.assertEqual((Path(directory) / 'originals' / self.category.image.name).read_bytes(), self.original)
            self.assertIn('saved_verified', report)
            self.assertIn('missing', report)

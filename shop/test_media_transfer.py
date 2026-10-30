from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from .models import Category, Product


class MediaTransferTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'products').mkdir()
        self.content = (settings.BASE_DIR / 'media/products/gallery-7.jpg').read_bytes()
        (self.root / 'products/original.jpg').write_bytes(self.content)
        category = Category.objects.create(name='Transfer fixture')
        self.product = Product.objects.create(name='Original', category=category, price=10, stock=1,
                                              image='products/original.jpg')

    def run_transfer(self, **kwargs):
        output = StringIO()
        call_command('transfer_media', source=str(self.root), stdout=output, **kwargs)
        return json.loads(output.getvalue())

    def test_audit_keeps_mapping_and_reports_missing_original(self):
        report = self.run_transfer()
        row = next(r for r in report['references'] if r['name'] == self.product.image.name)
        self.assertEqual(row['status'], 'valid_original')
        (self.root / 'products/original.jpg').unlink()
        with self.assertRaises(CommandError):
            self.run_transfer()
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, 'products/original.jpg')

    @override_settings(MEDIA_STORAGE='s3')
    def test_exact_key_conditional_upload(self):
        with patch('shop.management.commands.transfer_media.default_storage') as storage:
            storage.location = 'media'
            storage.bucket_name = 'fixture-bucket'
            self.run_transfer(upload=True)
            arguments = storage.connection.meta.client.put_object.call_args.kwargs
            self.assertEqual(arguments['Key'], 'media/products/original.jpg')
            self.assertEqual(arguments['IfNoneMatch'], '*')
            self.assertEqual(arguments['ContentType'], 'image/jpeg')

    @override_settings(MEDIA_STORAGE='s3')
    def test_collision_is_never_overwritten_or_renamed(self):
        with patch('shop.management.commands.transfer_media.default_storage') as storage:
            storage.location = 'media'
            storage.connection.meta.client.put_object.side_effect = ClientError(
                {'Error': {'Code': 'PreconditionFailed'}, 'ResponseMetadata': {'HTTPStatusCode': 412}}, 'PutObject')
            from io import BytesIO
            storage.open.return_value = BytesIO(b'other original')
            with self.assertRaises(CommandError):
                self.run_transfer(upload=True)
            storage.save.assert_not_called()
        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, 'products/original.jpg')

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from .models import Brand, Category, Product, Order, Banner
from .catalog_transfer import export_catalog, plan_catalog, apply_catalog


class CatalogTransferTests(TestCase):
    def test_internal_banner_link_uses_target_product_id(self):
        document = self.bundle()
        banner = Banner.objects.create(title='Transfer banner template', link='/products/')
        fields = export_catalog()['records']
        source = next(row for row in fields if row['model'] == 'Banner')
        source['fields']['title'] = 'New destination banner'
        source['fields']['link'] = '/product/99999/'
        document['records'].append(source)
        apply_catalog(document, Path(self.directory.name) / 'links-before.json')
        new = Product.objects.get(name='New transferred device')
        self.assertEqual(Banner.objects.get(title='New destination banner').link, f'/product/{new.pk}/')
        banner.refresh_from_db()
        self.assertEqual(banner.link, '/products/')

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.category = Category.objects.create(name='Transfer category')
        self.brand = Brand.objects.create(name='Transfer brand')
        self.product = Product.objects.create(name='Existing device', category=self.category, brand=self.brand, price=100, stock=1)
        self.user = User.objects.create_user('protected-customer', password='test-only-password')
        self.order = Order.objects.create(user=self.user, full_name='Customer', email='customer@example.test',
            phone='01700000000', address='Existing address', total_price=100, payment_status='paid')

    def bundle(self):
        document = export_catalog()
        existing = next(row for row in document['records'] if row['model'] == 'Product')
        row = copy.deepcopy(existing)
        row['source_id'] = 99999
        row['fields']['name'] = 'New transferred device'
        document['records'].append(row)
        return document

    def test_natural_key_import_remaps_ids_and_repeat_does_not_duplicate(self):
        document = self.bundle()
        plan, _, _ = plan_catalog(document)
        self.assertEqual(plan['summary']['create'], 1)
        self.assertEqual(Product.objects.count(), 1)
        apply_catalog(document, Path(self.directory.name) / 'before.json', expected_plan=plan)
        new = Product.objects.get(name='New transferred device')
        self.assertNotEqual(new.pk, 99999)
        self.assertEqual(new.category_id, self.category.pk)
        again, _, _ = plan_catalog(document)
        self.assertNotIn('create', again['summary'])
        apply_catalog(document, Path(self.directory.name) / 'repeat-before.json', expected_plan=again)
        self.assertEqual(Product.objects.count(), 2)

    def test_existing_catalog_stock_prices_and_private_records_are_preserved(self):
        document = self.bundle()
        existing = next(row for row in document['records'] if row['model'] == 'Product')
        existing['fields'].update(price='999', stock=999)
        plan = apply_catalog(document, Path(self.directory.name) / 'backup.json')
        self.assertEqual(plan['summary']['preserve_existing'], 1)
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.price, 100)
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(User.objects.get(pk=self.user.pk).username, 'protected-customer')
        backup = json.loads((Path(self.directory.name) / 'backup.json').read_text())
        self.assertNotIn('User', {row['model'] for row in backup['records']})
        self.assertNotIn('Order', {row['model'] for row in backup['records']})

    def test_ambiguous_target_and_source_keys_are_rejected(self):
        document = self.bundle()
        Product.objects.create(name=self.product.name, category=self.category, brand=self.brand, price=50)
        with self.assertRaises(ValueError):
            plan_catalog(document)
        with self.assertRaises(ValueError):
            plan_catalog(export_catalog())

    def test_private_models_and_unsafe_image_keys_are_rejected(self):
        document = self.bundle()
        document['records'].append({'model': 'Order', 'source_id': 99, 'fields': {}})
        with self.assertRaises(ValueError):
            plan_catalog(document)
        document = self.bundle()
        document['records'][-1]['fields']['image'] = '../private.jpg'
        with self.assertRaises(ValueError):
            plan_catalog(document)

    def test_backup_is_mandatory_and_never_overwritten(self):
        path = Path(self.directory.name) / 'existing-backup.json'
        path.write_text('preserved backup')
        with self.assertRaises(FileExistsError):
            apply_catalog(self.bundle(), path)
        self.assertEqual(path.read_text(), 'preserved backup')
        self.assertEqual(Product.objects.count(), 1)

    def test_changed_target_plan_and_invalid_product_leave_database_unchanged(self):
        document = self.bundle()
        plan, _, _ = plan_catalog(document)
        self.product.stock = 2
        self.product.save()
        with self.assertRaises(ValueError):
            apply_catalog(document, Path(self.directory.name) / 'stale.json', expected_plan=plan)
        document['records'][-1]['fields']['price'] = '-1'
        with self.assertRaises(ValidationError):
            apply_catalog(document, Path(self.directory.name) / 'invalid.json')
        self.assertEqual(Product.objects.count(), 1)

    def test_cli_is_read_only_without_apply_and_rejects_unreviewed_apply(self):
        from io import StringIO
        from django.core.management import CommandError
        path = Path(self.directory.name) / 'catalog.json'
        path.write_text(json.dumps(self.bundle()))
        call_command('catalog_import', str(path), stdout=StringIO())
        self.assertEqual(Product.objects.count(), 1)
        with self.assertRaises(CommandError):
            call_command('catalog_import', str(path), apply=True, stdout=StringIO())
        self.assertEqual(Product.objects.count(), 1)

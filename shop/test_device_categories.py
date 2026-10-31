from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import Category, Coupon, FooterGroup, HomeSection, NavigationItem, Product, ProductVariant, Brand


class DeviceCategoryTests(TestCase):
    def setUp(self):
        self.legacy = Category.objects.create(name='Phones & Tablets', featured=True)
        self.phones = Category.objects.create(name='Phones', featured=False)
        self.tablets = Category.objects.create(name='Tablets', parent=self.legacy, featured=False)
        self.phone = Product.objects.create(name='Galaxy S24 Ultra 5G', category=self.legacy, price=100)
        self.ipad = Product.objects.create(name='iPad Pro', category=self.legacy, price=200)
        self.existing_phone = Product.objects.create(name='iPhone 16', category=self.phones, price=100)
        self.existing_tablet = Product.objects.create(name='Existing tablet', category=self.tablets, price=100)
        self.variant = ProductVariant.objects.create(product=self.ipad, name='256GB', price=200, stock=2)
        self.phone_menu = NavigationItem.objects.create(label='Phones', category=self.legacy, page_title='Shop Phones')
        self.tablet_menu = NavigationItem.objects.create(label='Tablets', category=self.tablets)
        self.section = HomeSection.objects.create(title='Phones & Tablets', category=self.legacy)
        self.footer = FooterGroup.objects.create(title='Mobile devices')
        self.footer.categories.add(self.phones, self.legacy)
        self.coupon = Coupon.objects.create(code='DEVICES', value=10)
        self.coupon.categories.add(self.legacy)

    def split(self):
        migration = import_module('shop.migrations.0022_separate_phones_and_tablets')
        migration.separate_devices(apps, SimpleNamespace(connection=connection))

    def test_migration_preserves_records_and_repoints_all_category_links(self):
        self.split()
        self.split()  # A repeated application must not recreate or reclassify data.
        self.assertFalse(Category.objects.filter(name='Phones & Tablets').exists())
        self.assertEqual(Category.objects.get(name='Phones').pk, self.legacy.pk)
        self.tablets.refresh_from_db()
        self.assertIsNone(self.tablets.parent_id)
        for product in (self.phone, self.existing_phone):
            product.refresh_from_db()
            self.assertEqual(product.category_id, self.legacy.pk)
        for product in (self.ipad, self.existing_tablet):
            product.refresh_from_db()
            self.assertEqual(product.category_id, self.tablets.pk)
        self.assertEqual(Product.objects.count(), 4)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.product_id, self.ipad.pk)
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, 'Phones')
        for record in (self.coupon, self.footer):
            self.assertSetEqual(set(record.categories.values_list('pk', flat=True)), {self.legacy.pk, self.tablets.pk})

    def test_admin_choices_and_frontend_menus_use_separate_categories(self):
        self.split()
        admin_user = User.objects.create_superuser('admin', password='test-password')
        self.client.force_login(admin_user)
        response = self.client.get(reverse('admin:shop_product_add'))
        self.assertEqual(response.status_code, 200)
        names = set(response.context['adminform'].form.fields['category'].queryset.values_list('name', flat=True))
        self.assertTrue({'Phones', 'Tablets'} <= names)
        self.assertNotIn('Phones & Tablets', names)
        self.assertContains(response, 'Choose Phones for mobile phones and Tablets for iPads')
        for item, expected in [(self.phone_menu, {self.phone.pk, self.existing_phone.pk}),
                               (self.tablet_menu, {self.ipad.pk, self.existing_tablet.pk})]:
            item.refresh_from_db()
            page = self.client.get(reverse('product_list'), {'category': item.category_id})
            self.assertEqual(page.status_code, 200)
            self.assertSetEqual({p.pk for p in page.context['products']}, expected)
            menu = next(c for c in page.context['nav_categories'] if c.name == item.label)
            self.assertIn(f'category={item.category_id}', menu.nav_url)
        legacy_page = self.client.get(reverse('phones_tablets'))
        self.assertSetEqual({p.pk for p in legacy_page.context['products']}, {self.phone.pk, self.existing_phone.pk})

    def test_navigation_setup_never_targets_combined_category(self):
        NavigationItem.objects.all().delete()
        Brand.objects.create(name='Apple')
        call_command('configure_primary_navigation', apply=True, verbosity=0)
        self.assertEqual(NavigationItem.objects.get(label='Phones').category_id, self.phones.pk)
        self.assertEqual(NavigationItem.objects.get(label='Tablets').category_id, self.tablets.pk)

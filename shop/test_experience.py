import csv
import io
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .catalog_csv import export_csv, parse_csv, validate_rows
from .forms import PreOrderForm
from .models import (Category, Brand, Product, ProductVariant, Order, OrderItem, ProductPurpose,
    Compatibility, PriceAlert, StockAlert, CustomerNotification, ServiceClaim, ClaimEvent,
    ProductWarranty, CatalogActivity, RefundRecord, Preorder)


class ShoppingExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('tools-customer', email='customer@example.test', password='test-password')
        cls.other = User.objects.create_user('tools-other', password='test-password')
        cls.admin = User.objects.create_superuser('tools-admin', email='admin@example.test', password='test-password')
        cls.category = Category.objects.create(name='Tools devices')
        cls.device = Product.objects.create(name='Study phone', category=cls.category, price=100, stock=5)
        cls.accessory = Product.objects.create(name='Charger', category=cls.category, price=20, stock=3)
        cls.variable = Product.objects.create(name='Options', category=cls.category, price=1, stock=100)
        cls.v1 = ProductVariant.objects.create(product=cls.variable, name='8GB / Black', ram='8GB', storage='128GB', color='Black', warranty='Official 1 year', price=150, stock=2)
        cls.v2 = ProductVariant.objects.create(product=cls.variable, name='16GB / Blue', ram='16GB', storage='256GB', color='Blue', warranty='Seller 6 months', price=250, stock=0)
        cls.order = Order.objects.create(user=cls.user, full_name='Customer', email='customer@example.test', address='Dhaka', phone='01700000000', total_price=100, subtotal=100, payment_method='COD', payment_status='paid', status='delivered')
        cls.line = OrderItem.objects.create(order=cls.order, product=cls.device, product_name=cls.device.name, price=90, quantity=1)

    def test_finder_uses_verified_purpose_actual_variant_budget_and_tracked_stock(self):
        ProductPurpose.objects.create(product=self.device, purpose='study', reason='Verified study features', verified=True)
        ProductPurpose.objects.create(product=self.accessory, purpose='study', reason='Draft', verified=False)
        ProductPurpose.objects.create(product=self.variable, purpose='study', reason='Verified option', verified=True)
        page = self.client.get(reverse('gadget_finder'), {'budget': '200', 'purpose': 'study'})
        self.assertEqual(page.status_code, 200)
        self.assertEqual([m['product'].pk for m in page.context['matches']], [self.device.pk, self.variable.pk])
        self.assertEqual(page.context['matches'][1]['option'].pk, self.v1.pk)
        self.assertEqual(len(self.client.get(reverse('gadget_finder'), {'budget': '99', 'purpose': 'study'}).context['matches']), 0)
        self.assertFalse(self.client.get(reverse('gadget_finder'), {'budget': 'NaN', 'purpose': 'study'}).context['form'].is_valid())
        self.device.stock = None
        self.device.save()
        self.assertEqual(len(self.client.get(reverse('gadget_finder'), {'budget': '200', 'purpose': 'study'}).context['matches']), 1)

    def test_ram_color_and_warranty_filters_match_one_variant(self):
        params = {'option_ram': '8GB', 'option_color': 'Black', 'option_warranty': 'Official 1 year'}
        page = self.client.get(reverse('product_list'), params)
        self.assertEqual([p.pk for p in page.context['products']], [self.variable.pk])
        params['option_warranty'] = 'Seller 6 months'
        self.assertFalse(list(self.client.get(reverse('product_list'), params).context['products']))

    def test_compatibility_unknown_negative_and_curated_pair_cart_are_authoritative(self):
        params = {'device': self.device.pk, 'accessory': self.accessory.pk}
        self.assertContains(self.client.get(reverse('compatibility_checker'), params), 'Compatibility not confirmed')
        pair = Compatibility.objects.create(device=self.device, accessory=self.accessory, verified=True, compatible=False, evidence='Different connector', bought_together=True)
        self.assertContains(self.client.get(reverse('compatibility_checker'), params), 'Verified incompatible')
        self.assertEqual(self.client.post(reverse('add_pair', args=[pair.pk])).status_code, 404)
        pair.compatible = True
        pair.save()
        self.accessory.stock = 0
        self.accessory.save()
        self.client.post(reverse('add_pair', args=[pair.pk]))
        self.assertFalse(self.client.session.get('cart'))
        self.accessory.stock = 3
        self.accessory.save()
        self.client.post(reverse('add_pair', args=[pair.pk]))
        self.assertEqual(self.client.session['cart'], {str(self.device.pk): 1, str(self.accessory.pk): 1})
        self.assertContains(self.client.get(reverse('product_detail', args=[self.device.pk])), 'Frequently bought together')

    def test_buy_again_preserves_privacy_checks_current_stock_and_prices(self):
        url = reverse('buy_again', args=[self.order.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse('cart_view'))
        page = self.client.get(reverse('cart_view'))
        self.assertEqual(page.context['items'][0]['price'], Decimal('100'))
        self.device.stock = 0
        self.device.save()
        before = self.client.session['cart']
        self.client.post(url)
        self.assertEqual(self.client.session['cart'], before)

    def test_buy_again_does_not_substitute_deleted_or_changed_variant(self):
        self.line.product = self.variable
        self.line.variant_name = 'Removed old option'
        self.line.sku = 'OLD'
        self.line.save()
        self.client.force_login(self.user)
        self.client.post(reverse('buy_again', args=[self.order.pk]))
        self.assertFalse(self.client.session.get('cart'))

    def test_guest_claim_access_and_duplicate_submission_are_safe(self):
        self.order.user = None
        self.order.save()
        url = reverse('order_services', args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        session = self.client.session
        session['guest_order_ids'] = [self.order.pk]
        session.save()
        page = self.client.get(url)
        token = page.context['form']['token'].value()
        data = {'item': self.line.pk, 'kind': 'return', 'reason': 'The item has a verified issue.', 'token': token}
        self.assertRedirects(self.client.post(url, data), url)
        self.client.post(url, data)
        self.assertEqual(ServiceClaim.objects.count(), 1)
        self.assertEqual(ClaimEvent.objects.count(), 1)
        claim = ServiceClaim.objects.get()
        claim.status, claim.customer_update, claim.staff_notes = 'reviewing', 'Please send the serial number.', 'PRIVATE STAFF NOTE'
        claim.save()
        page = self.client.get(url)
        self.assertContains(page, 'Please send the serial number.')
        self.assertNotContains(page, 'PRIVATE STAFF NOTE')
        self.assertEqual(claim.events.count(), 2)
        self.client.force_login(self.other)
        session = self.client.session
        session.pop('guest_order_ids')
        session.save()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_claim_rejects_other_order_item_and_undelivered_order(self):
        self.client.force_login(self.user)
        url = reverse('order_services', args=[self.order.pk])
        page = self.client.get(url)
        data = {'item': 99999, 'kind': 'warranty', 'reason': 'Please check the broken item.', 'token': page.context['form']['token'].value()}
        self.client.post(url, data)
        self.assertFalse(ServiceClaim.objects.exists())
        self.order.status = 'received'
        self.order.save()
        data['item'] = self.line.pk
        self.assertContains(self.client.post(url, data), 'Requests are available after delivery')
        self.assertFalse(ServiceClaim.objects.exists())

    def test_variant_price_alert_validation_and_ownership(self):
        self.client.force_login(self.user)
        url = reverse('subscribe_price', args=[self.variable.pk])
        self.client.post(url, {'target_price': '100'})
        self.assertFalse(PriceAlert.objects.exists())
        self.client.post(url, {'variant': self.v1.pk, 'target_price': '150'})
        self.assertFalse(PriceAlert.objects.exists())
        self.client.post(url, {'variant': self.v1.pk, 'target_price': '120'})
        alert = PriceAlert.objects.get()
        self.assertEqual(alert.user, self.user)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('shopping_notifications'), {'action': 'cancel', 'alert': alert.pk}).status_code, 404)
        self.assertTrue(PriceAlert.objects.exists())

    def test_scheduled_alerts_are_private_and_deduplicated(self):
        price = PriceAlert.objects.create(user=self.user, product=self.variable, variant=self.v1, target_price=120)
        stock = StockAlert.objects.create(user=self.user, product=self.accessory, email='customer@example.test')
        call_command('process_shopping_alerts', verbosity=0)
        self.assertEqual(CustomerNotification.objects.count(), 1)
        self.v1.price = 110
        self.v1.save()
        call_command('process_shopping_alerts', verbosity=0)
        call_command('process_shopping_alerts', verbosity=0)
        self.assertEqual(CustomerNotification.objects.count(), 2)
        price.refresh_from_db()
        self.assertFalse(price.active)
        self.assertIsNotNone(price.triggered_at)
        self.client.force_login(self.other)
        self.assertEqual(len(self.client.get(reverse('shopping_notifications')).context['notifications']), 0)
        self.client.force_login(self.user)
        self.client.post(reverse('shopping_notifications'))
        self.assertFalse(CustomerNotification.objects.filter(read=False).exists())

    @override_settings(STOCK_ALERT_EMAIL_READY=True, DEFAULT_FROM_EMAIL='store@example.test', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_price_email_failure_preserves_pending_delivery(self):
        alert = PriceAlert.objects.create(user=self.user, product=self.device, target_price=100, email='customer@example.test')
        with patch('shop.management.commands.process_shopping_alerts.send_mail', return_value=0):
            with self.assertRaises(CommandError):
                call_command('process_shopping_alerts', email=True, verbosity=0)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.triggered_at)
        self.assertIsNone(alert.email_sent_at)
        call_command('process_shopping_alerts', email=True, verbosity=0)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.email_sent_at)

    def test_comparison_includes_verified_warranty_and_option_details(self):
        ProductWarranty.objects.create(product=self.variable, warranty_type='manufacturer', period_en='1 year', is_verified=True)
        session = self.client.session
        session['compare_ids'] = [self.variable.pk, self.device.pk]
        session.save()
        page = self.client.get(reverse('compare'))
        self.assertContains(page, 'Manufacturer · 1 year')
        self.assertContains(page, 'Not confirmed')
        self.assertContains(page, 'Official 1 year')
        self.assertContains(page, '8GB')

    def test_preorder_customer_cannot_set_status_or_advance_receipt(self):
        self.assertNotIn('advance_status', PreOrderForm().fields)
        self.assertNotIn('status', PreOrderForm().fields)
        entry = Preorder.objects.create(user=self.user, name='Buyer', product_name='Future device', estimated_arrival='2027-01-01', status='confirmed', advance_amount=100, advance_status='verified', cancellation_terms='Refundable before dispatch')
        self.client.force_login(self.user)
        page = self.client.get(reverse('order_history'))
        self.assertContains(page, 'Refundable before dispatch')
        self.assertContains(page, 'Receipt verified')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('order_history')), 'Future device')

    def csv_rows(self, kind='product'):
        return list(csv.DictReader(io.StringIO(export_csv(kind))))

    def upload(self, kind, rows):
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return self.client.post(reverse('catalog_transfer'), {'kind': kind, 'file': SimpleUploadedFile('catalog.csv', out.getvalue().encode())})

    def test_csv_preview_does_not_write_apply_audits_actor_and_blocks_stale_data(self):
        self.client.force_login(self.admin)
        rows = self.csv_rows()
        row = next(row for row in rows if row['id'] == str(self.device.pk))
        row['price'] = '120'
        page = self.upload('product', [row])
        self.assertTrue(page.context['can_apply'])
        self.device.refresh_from_db()
        self.assertEqual(self.device.price, 100)
        self.client.post(reverse('catalog_transfer'), {'action': 'apply'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.price, 120)
        event = CatalogActivity.objects.get(model='shop.Product', object_id=str(self.device.pk))
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertEqual(event.changes['price']['after'], '120')
        row['price'] = '130'
        self.upload('product', [row])
        self.device.price = 140
        self.device.save()
        self.client.post(reverse('catalog_transfer'), {'action': 'apply'})
        self.device.refresh_from_db()
        self.assertEqual(self.device.price, 140)

    def test_csv_invalid_row_and_permissions_prevent_all_mutations(self):
        rows = self.csv_rows('variant')
        rows[0]['stock'] = '-1'
        self.client.force_login(self.admin)
        page = self.upload('variant', rows)
        self.assertFalse(page.context['can_apply'])
        self.assertTrue(page.context['results'][0]['errors'])
        self.client.post(reverse('catalog_transfer'), {'action': 'apply'})
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.stock, 2)
        with self.assertRaises(PermissionDenied):
            validate_rows('variant', rows, self.other)

    def test_brand_and_variant_exports_roundtrip_and_bound_uploads(self):
        Brand.objects.create(name='=SUM(1,2)')
        for kind in ('brand', 'variant'):
            exported = export_csv(kind)
            upload = SimpleUploadedFile('catalog.csv', exported.encode())
            rows = parse_csv(kind, upload)
            self.assertFalse(any(row['errors'] for row in validate_rows(kind, rows, self.admin)))
        self.assertIn('\t=SUM', export_csv('brand'))
        with self.assertRaises(ValidationError):
            parse_csv('brand', SimpleUploadedFile('bad.csv', b'wrong\nheader\n'))

    def test_dashboard_permissions_totals_and_low_variant_stock(self):
        self.assertEqual(self.client.get(reverse('store_dashboard')).status_code, 302)
        self.client.force_login(self.admin)
        page = self.client.get(reverse('store_dashboard'))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['collected'], 100)
        self.assertIn(self.v2, page.context['low_variants'])
        RefundRecord.objects.create(order=self.order, amount=20, reference='REF-1', note='Confirmed refund', recorded_by=self.admin)
        page = self.client.get(reverse('store_dashboard'))
        self.assertEqual(page.context['net_collected'], 80)
        with self.assertRaises(ValidationError):
            RefundRecord(order=self.order, amount=90, reference='REF-2', note='Too large').full_clean()
        self.assertContains(self.client.get(reverse('admin:index')), 'Store operations')

    def test_mutation_endpoints_require_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for name, args in [('subscribe_price', [self.device.pk]), ('buy_again', [self.order.pk]), ('order_services', [self.order.pk]), ('shopping_notifications', [])]:
            self.assertEqual(strict.post(reverse(name, args=args)).status_code, 403)

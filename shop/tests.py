from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.core import mail
from django.core.management import call_command, CommandError
from django.urls import reverse
from .models import (Banner, Brand, Category, HomeSection, Offer, Order, OrderItem,
                     Preorder, Product, ProductVariant, SectionProduct, StoreSettings, Wishlist)
from .models import Coupon, CouponRedemption, SavedAddress, StockAlert
from .services import cart_lines, checkout_totals


class ShoppingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('customer', 'customer@example.com', 'test-password')
        cls.other = User.objects.create_user('other', 'other@example.com', 'test-password')
        cls.category = Category.objects.create(name='Phones')
        cls.child = Category.objects.create(name='Smartphones', parent=cls.category)
        cls.brand = Brand.objects.create(name='Test Brand')
        cls.product = Product.objects.create(name='Test phone', category=cls.child, brand=cls.brand,
                                             price=100, compare_at_price=120, stock=5)
        cls.second = Product.objects.create(name='Another phone', category=cls.category, price=50, stock=1)
        cls.variable = Product.objects.create(name='Variant phone', category=cls.child, price=75, stock=0)
        cls.variant = ProductVariant.objects.create(product=cls.variable, name='Black / 256GB', sku='BLK256', price=150,
                                                    stock=3)
        cls.empty_variant = ProductVariant.objects.create(product=cls.variable, name='Blue / 512GB', price=200, stock=0)
        cls.store = StoreSettings.objects.get(pk=1)
        cls.store.shipping_price = Decimal('25')
        cls.store.save()

    def add(self, product=None, qty=1, variant=None):
        data = {'quantity': str(qty)}
        if variant:
            data['variant'] = str(variant.pk)
        return self.client.post(reverse('add_to_cart', args=[(product or self.product).pk]), data,
                                HTTP_ACCEPT='application/json')

    def test_live_wishlist_state_privacy_and_fallback(self):
        url = reverse('toggle_wishlist', args=[self.product.pk])
        self.assertEqual(self.client.post(url, HTTP_ACCEPT='application/json').status_code, 401)
        self.assertFalse(Wishlist.objects.exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(url, HTTP_ACCEPT='application/json').status_code, 403)
        result = self.client.post(url, HTTP_ACCEPT='application/json')
        self.assertTrue(result.json()['saved'])
        self.assertContains(self.client.get(reverse('product_detail', args=[self.product.pk])), 'aria-pressed="true"')
        self.assertIn(self.product.pk, self.client.get(reverse('product_list')).context['wishlist_ids'])
        self.client.force_login(self.other)
        self.assertNotIn(self.product.pk, self.client.get(reverse('product_list')).context['wishlist_ids'])
        self.client.force_login(self.user)
        self.assertFalse(self.client.post(url, HTTP_ACCEPT='application/json').json()['saved'])
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=self.product).exists())
        self.assertRedirects(self.client.post(url), reverse('wishlist'))

    def checkout_data(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 200)
        return {'checkout_token': self.client.session['checkout_token'], 'full_name': 'Customer',
                'email': 'customer@example.com', 'address': 'Dhaka', 'phone': '01700000000', 'payment_method': 'COD'}

    def test_comparison_limit_post_only_and_real_specs(self):
        self.product.specifications = {'Storage': '256GB'}
        self.product.save()
        products = [self.product, self.second, self.variable, Product.objects.create(name='Fourth', category=self.category, price=20)]
        for product in products:
            self.assertEqual(self.client.post(reverse('compare_toggle', args=[product.pk]), HTTP_ACCEPT='application/json').status_code, 200)
        fifth = Product.objects.create(name='Fifth', category=self.category, price=30)
        self.assertEqual(self.client.post(reverse('compare_toggle', args=[fifth.pk]), HTTP_ACCEPT='application/json').status_code, 400)
        self.assertEqual(len(self.client.session['compare_ids']), 4)
        self.assertContains(self.client.get(reverse('compare')), '256GB')
        self.assertEqual(self.client.get(reverse('compare_toggle', args=[self.product.pk])).status_code, 405)

    def test_coupon_checkout_totals_redemption_and_duplicate_order(self):
        coupon = Coupon.objects.create(code='WELCOME', kind='percent', value=10, minimum_order=100, usage_limit=1)
        self.add(qty=2)
        data = self.checkout_data()
        data['coupon_code'] = 'welcome'
        response = self.client.post(reverse('checkout'), data)
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, Decimal('205'))
        self.assertEqual(order.coupon_discount, Decimal('20'))
        self.assertEqual(order.items.get().price, Decimal('100'))
        self.assertEqual(order.status_events.count(), 1)
        self.client.post(reverse('checkout'), data)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(CouponRedemption.objects.count(), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.client.force_login(self.other)
        self.add()
        self.client.get(reverse('checkout'))
        other_data = {**data, 'checkout_token': self.client.session['checkout_token']}
        self.assertEqual(self.client.post(reverse('checkout'), other_data).status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_new_mutation_endpoints_require_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for route, args in [('compare_toggle', [self.product.pk]), ('apply_coupon', []),
                            ('profile', []), ('subscribe_stock', [self.variable.pk])]:
            self.assertEqual(strict.post(reverse(route, args=args)).status_code, 403)

    def test_coupon_rules_expiry_eligibility_minimum_and_cap(self):
        coupon = Coupon.objects.create(code='TEST', kind='fixed', value=1000)
        self.add(qty=1)
        lines = cart_lines(self.client.session)
        def totals():
            return checkout_totals(lines, self.user, 'TEST')
        self.assertEqual(totals()['grand_total'], Decimal('25'))
        coupon.minimum_order = 101
        coupon.save()
        self.assertTrue(totals()['coupon_error'])
        coupon.minimum_order = 0
        coupon.ends_at = timezone.now() - timedelta(seconds=1)
        coupon.save()
        self.assertTrue(totals()['coupon_error'])
        coupon.ends_at = None
        coupon.starts_at = timezone.now() + timedelta(days=1)
        coupon.save()
        self.assertTrue(totals()['coupon_error'])
        coupon.starts_at = None
        coupon.save()
        coupon.products.add(self.second)
        self.assertTrue(totals()['coupon_error'])
        coupon.categories.add(self.child)
        self.assertFalse(totals()['coupon_error'])
        coupon.customers.add(self.other)
        self.assertTrue(totals()['coupon_error'])
        coupon.customers.clear()
        coupon.active = False
        coupon.save()
        self.assertTrue(totals()['coupon_error'])

    def test_coupon_failure_rolls_back_and_preview_does_not_order(self):
        coupon = Coupon.objects.create(code='LIMIT', kind='fixed', value=10, per_customer_limit=1)
        self.add()
        data = self.checkout_data()
        data['coupon_code'] = coupon.code
        preview = self.client.post(reverse('checkout'), {**data, 'action': 'preview'})
        self.assertEqual(preview.context['grand_total'], Decimal('115'))
        self.assertFalse(Order.objects.exists())
        with patch('shop.services.OrderItem.objects.create', side_effect=ValidationError('Write failed')):
            self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        coupon.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(coupon.used_count, 0)
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(CouponRedemption.objects.exists())
        self.client.post(reverse('checkout'), data)
        self.add()
        second_data = self.checkout_data()
        second_data['coupon_code'] = coupon.code
        self.assertEqual(self.client.post(reverse('checkout'), second_data).status_code, 400)

    def test_address_dashboard_ownership_and_checkout_prefill(self):
        address = SavedAddress.objects.create(user=self.user, label='Home', full_name='Customer', phone='01700000000', address='Dhaka')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('profile'), {'edit': address.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse('delete_address', args=[address.pk])).status_code, 404)
        self.add()
        self.assertEqual(self.client.get(reverse('checkout'), {'address': address.pk}).status_code, 404)
        self.client.force_login(self.user)
        self.add()
        self.assertEqual(self.client.get(reverse('checkout'), {'address': address.pk}).context['form'].initial['address'], 'Dhaka')
        self.assertContains(self.client.get(reverse('profile')), 'Home')
        self.assertEqual(self.client.get(reverse('delete_address', args=[address.pk])).status_code, 405)
        self.assertEqual(self.client.get('/admin/shop/coupon/').status_code, 302)

    def test_stock_alert_subscription_validation_and_ownership(self):
        url = reverse('subscribe_stock', args=[self.variable.pk])
        self.assertEqual(self.client.post(url, {'email': 'test@example.com'}).status_code, 302)
        self.assertFalse(StockAlert.objects.exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'email': 'bad', 'variant': self.empty_variant.pk})
        self.assertFalse(StockAlert.objects.exists())
        self.client.post(url, {'email': 'test@example.com', 'variant': self.variant.pk})
        self.assertFalse(StockAlert.objects.exists())
        self.client.post(url, {'email': 'test@example.com', 'variant': self.empty_variant.pk})
        self.client.post(url, {'email': 'test@example.com', 'variant': self.empty_variant.pk})
        self.assertEqual(StockAlert.objects.count(), 1)
        alert = StockAlert.objects.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('unsubscribe_stock', args=[alert.pk])).status_code, 404)
        self.client.force_login(self.user)
        self.client.post(reverse('unsubscribe_stock', args=[alert.pk]))
        alert.refresh_from_db()
        self.assertFalse(alert.active)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', STOCK_ALERT_EMAIL_READY=True,
                       DEFAULT_FROM_EMAIL='store@example.com', STOREFRONT_URL='https://store.example.com')
    def test_stock_email_only_after_restock_and_once(self):
        alert = StockAlert.objects.create(user=self.user, product=self.variable, variant=self.empty_variant, email='test@example.com')
        call_command('send_stock_alerts', verbosity=0)
        self.assertEqual(len(mail.outbox), 0)
        self.empty_variant.stock = 2
        self.empty_variant.save()
        call_command('send_stock_alerts', verbosity=0)
        call_command('send_stock_alerts', verbosity=0)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.variable.name, mail.outbox[0].subject)

    @override_settings(STOCK_ALERT_EMAIL_READY=True, DEFAULT_FROM_EMAIL='store@example.com')
    def test_stock_email_failure_remains_pending(self):
        alert = StockAlert.objects.create(user=self.user, product=self.product, email='test@example.com')
        with patch('shop.management.commands.send_stock_alerts.send_mail', side_effect=OSError('Unavailable')):
            with self.assertRaises(CommandError):
                call_command('send_stock_alerts')
        alert.refresh_from_db()
        self.assertTrue(alert.active)
        self.assertIsNone(alert.sent_at)
        with override_settings(STOCK_ALERT_EMAIL_READY=False):
            with self.assertRaises(CommandError):
                call_command('send_stock_alerts')

    def test_offer_schedule_and_admin_timeline(self):
        future = Offer.objects.create(title='Scheduled future', description='Future', starts_at=timezone.now() + timedelta(days=1))
        expired = Offer.objects.create(title='Expired offer', description='Past', ends_at=timezone.now() - timedelta(days=1))
        active = Offer.objects.create(title='Scheduled current', description='Current', ends_at=timezone.now() + timedelta(days=1))
        response = self.client.get(reverse('offers'))
        self.assertContains(response, active.title)
        self.assertNotContains(response, future.title)
        self.assertNotContains(response, expired.title)
        self.assertContains(response, 'data-countdown')
        self.add()
        self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get(user=self.user)
        self.assertContains(self.client.get(reverse('order_detail', args=[order.pk])), 'Received')
        from django.contrib.admin.sites import AdminSite
        from .admin import OrderAdmin
        order.status = 'shipped'
        OrderAdmin(Order, AdminSite()).save_model(None, order, type('Form', (), {'changed_data': ['status']})(), True)
        self.assertEqual(order.status_events.last().status, 'shipped')

    def test_quick_view_drawer_availability_and_browsing_history(self):
        self.assertContains(self.client.get(reverse('quick_view', args=[self.variable.pk])), self.variant.sku)
        self.add(qty=2)
        self.assertContains(self.client.get(reverse('cart_drawer')), '225.00')
        available = self.client.get(reverse('product_list'), {'availability': 'available'})
        self.assertIn(self.variable, list(available.context['products']))
        self.assertEqual(self.client.get(reverse('product_list'), {'availability': 'out'}).context['page_obj'].paginator.count, 0)
        self.client.get(reverse('product_detail', args=[self.product.pk]))
        response = self.client.get(reverse('product_detail', args=[self.second.pk]))
        self.assertEqual(response.context['recently_viewed'][0].pk, self.product.pk)
        self.assertEqual(Client().get(reverse('product_detail', args=[self.second.pk])).context['recently_viewed'], [])

    def test_ajax_section_has_no_invisible_grid_cell(self):
        section = HomeSection.objects.create(title='Grid regression')
        SectionProduct.objects.create(section=section, product=self.product)
        html = self.client.get(reverse('home_section', args=[section.pk])).json()['html']
        self.assertNotIn('\ufeff', html)
        self.assertTrue(html.lstrip().startswith('<article'))

    def test_comparison_explicit_actions_prune_missing_values_and_clear(self):
        self.product.specifications = {'Storage': '256GB', 'Weight': '', 'Ports': 0}
        self.product.save()
        session = self.client.session
        session['compare_ids'] = [self.product.pk, self.product.pk, 999999, True, 'bad', self.second.pk]
        session.save()
        response = self.client.get(reverse('compare'))
        self.assertEqual(response.context['compare_ids'], [self.product.pk, self.second.pk])
        rows = {row['label']: row['values'] for row in response.context['rows']}
        self.assertEqual(rows['Storage'], ['256GB', 'Not provided'])
        self.assertEqual(rows['Weight'], ['Not provided', 'Not provided'])
        self.assertEqual(rows['Ports'], [0, 'Not provided'])
        url = reverse('compare_toggle', args=[self.variable.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'action': 'add'}, HTTP_ACCEPT='application/json').status_code, 200)
        self.assertEqual(self.client.session['compare_ids'], [self.product.pk, self.second.pk, self.variable.pk])
        for _ in range(2):
            self.client.post(url, {'action': 'remove'}, HTTP_ACCEPT='application/json')
        self.assertEqual(len(self.client.session['compare_ids']), 2)
        self.assertEqual(Client().get(reverse('compare')).context['compare_ids'], [])
        self.assertEqual(self.client.get(reverse('compare_clear')).status_code, 405)
        result = self.client.post(reverse('compare_clear'), HTTP_ACCEPT='application/json').json()
        self.assertEqual(result['ids'], [])
        self.assertIn('Your comparison is empty.', result['html'])

    def test_wishlist_idempotent_saves_ownership_and_new_session(self):
        url = reverse('toggle_wishlist', args=[self.product.pk])
        self.assertContains(self.client.get(reverse('wishlist')), 'Sign in to your wishlist')
        self.client.force_login(self.user)
        for _ in range(3):
            result = self.client.post(url, {'action': 'save', 'user_id': self.other.pk}, HTTP_ACCEPT='application/json').json()
            self.assertTrue(result['saved'])
            self.assertEqual(result['wishlist_count'], 1)
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 1)
        fresh = Client()
        fresh.force_login(self.user)
        self.assertContains(fresh.get(reverse('wishlist')), self.product.name)
        self.assertEqual(fresh.get(reverse('wishlist'), HTTP_ACCEPT='application/json').json()['wishlist_ids'], [self.product.pk])
        self.client.force_login(self.other)
        self.client.post(url, {'action': 'remove', 'user_id': self.user.pk}, HTTP_ACCEPT='application/json')
        self.assertTrue(Wishlist.objects.filter(user=self.user, product=self.product).exists())
        self.assertEqual(self.client.get(reverse('wishlist'), HTTP_ACCEPT='application/json').json()['wishlist_ids'], [])
        for _ in range(2):
            result = fresh.post(url, {'action': 'remove'}, HTTP_ACCEPT='application/json').json()
            self.assertFalse(result['saved'])
            self.assertEqual(result['wishlist_count'], 0)

    def test_cart_snapshot_variant_images_totals_and_rejected_quantity(self):
        self.variant.image = 'variant_images/real-option.png'
        self.variant.save()
        response = self.add(self.variable, qty=2, variant=self.variant).json()
        self.assertEqual(response['cart_count'], 2)
        self.assertEqual(Decimal(response['subtotal']), Decimal('300'))
        self.assertEqual(Decimal(response['total']), Decimal('325'))
        self.assertIn('variant_images/real-option.png', response['drawer_html'])
        self.assertIn(self.variant.sku, response['drawer_html'])
        self.assertIn('300.00', response['cart_html'])
        key = f'{self.variable.pk}:{self.variant.pk}'
        result = self.client.post(reverse('update_cart'), {'qty_' + key: '4'}, HTTP_ACCEPT='application/json')
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json()['cart_count'], 2)
        self.assertEqual(self.client.session['cart'][key], 2)
        result = self.client.post(reverse('update_cart'), {'qty_' + key: '0'}, HTTP_ACCEPT='application/json').json()
        self.assertEqual(result['cart_count'], 0)
        self.assertEqual(Decimal(result['total']), Decimal('0'))
        self.assertIn('Your bag is empty.', result['drawer_html'])

    def test_cart_snapshot_coupon_consistency_and_invalid_checkout_link(self):
        self.add(qty=2)
        self.client.force_login(self.user)
        self.add(qty=2)
        Coupon.objects.create(code='CART10', kind='percent', value=10)
        session = self.client.session
        session['coupon_code'] = 'CART10'
        session.save()
        response = self.client.get(reverse('cart_drawer'), HTTP_ACCEPT='application/json').json()
        self.assertEqual(Decimal(response['total']), self.client.get(reverse('cart_view')).context['grand_total'])
        self.assertIn('CART10', response['drawer_html'])
        self.product.stock = 0
        self.product.save()
        result = self.client.get(reverse('cart_drawer'), HTTP_ACCEPT='application/json').json()
        self.assertNotIn('Continue to checkout', result['drawer_html'])
        self.assertIn('Update unavailable items', result['drawer_html'])
        strict = Client(enforce_csrf_checks=True)
        for route, args in [('compare_clear', []), ('toggle_wishlist', [self.product.pk]), ('update_cart', []), ('remove_from_cart', [self.product.pk])]:
            self.assertEqual(strict.post(reverse(route, args=args)).status_code, 403)

    def test_server_totals_cart_counts_and_quantities(self):
        self.assertEqual(self.add(qty=2).json()['total'], '225.00')
        response = self.client.get(reverse('cart_view'))
        self.assertEqual(response.context['subtotal'], Decimal('200'))
        self.assertEqual(response.context['savings'], Decimal('40'))
        self.assertContains(self.client.get('/'), 'aria-label="Cart, 2 items"')
        for qty in [-1, 0, 100, '2.5', 'bad', 6]:
            self.assertEqual(self.add(qty=qty).status_code, 400)
        self.assertEqual(self.client.session['cart'][str(self.product.pk)], 2)

    def test_post_only_and_csrf(self):
        for route, args in [('add_to_cart', [self.product.pk]), ('remove_from_cart', [self.product.pk]),
                            ('clear_cart', []), ('update_cart', [])]:
            self.assertEqual(self.client.get(reverse(route, args=args)).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('add_to_cart', args=[self.product.pk])).status_code, 403)
        strict.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(strict.post(reverse('add_to_cart', args=[self.product.pk]),
                                     {'csrfmiddlewaretoken': strict.cookies['csrftoken'].value}).status_code, 302)

    def test_variants_and_cart_update_removal(self):
        self.assertEqual(self.add(self.variable).status_code, 400)
        self.assertEqual(self.add(self.product, variant=self.variant).status_code, 400)
        self.assertEqual(self.add(self.variable, variant=self.empty_variant).status_code, 400)
        self.assertEqual(self.add(self.variable, qty=2, variant=self.variant).json()['total'], '325.00')
        key = f'{self.variable.pk}:{self.variant.pk}'
        self.assertEqual(
            self.client.post(reverse('update_cart'), {'qty_' + key: '4'}, HTTP_ACCEPT='application/json').status_code,
            400)
        self.assertEqual(self.client.session['cart'][key], 2)
        self.client.post(reverse('update_cart'), {'qty_' + key: '1'})
        self.assertEqual(self.client.session['cart'][key], 1)
        self.client.post(reverse('remove_from_cart', args=[self.variable.pk]), {'key': key})
        self.assertEqual(self.client.session['cart'], {})

    def test_checkout_server_totals_snapshots_stock_and_idempotency(self):
        self.add(qty=2)
        data = self.checkout_data()
        data.update({'price': '1', 'total_price': '1', 'shipping': '0'})
        response = self.client.post(reverse('checkout'), data)
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total_price, Decimal('225'))
        self.assertEqual(order.savings, Decimal('40'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(order.items.get().product_name, 'Test phone')
        self.assertEqual(order.payment_status, 'pending')
        repeat = self.client.post(reverse('checkout'), data)
        self.assertEqual(response.url, repeat.url)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.add(self.second)
        self.client.post(reverse('checkout'), data)
        self.assertEqual(self.client.session['cart'][str(self.second.pk)], 1)

    def test_variant_purchase_uses_actual_price_name_and_stock(self):
        self.add(self.variable, qty=2, variant=self.variant)
        self.client.post(reverse('checkout'), self.checkout_data())
        item = OrderItem.objects.get(order__user=self.user)
        self.assertEqual(item.price, Decimal('150'))
        self.assertEqual(item.variant_name, 'Black / 256GB')
        self.assertEqual(item.sku, 'BLK256')
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 1)

    def test_changed_stock_rejects_checkout_and_preserves_cart(self):
        self.add(qty=2)
        data = self.checkout_data()
        Product.objects.filter(pk=self.product.pk).update(stock=1)
        self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.session['cart'][str(self.product.pk)], 2)

    def test_transaction_rolls_back_partial_reservations(self):
        self.add()
        self.add(self.second)
        data = self.checkout_data()
        original_create = OrderItem.objects.create
        calls = []

        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise ValidationError('Simulated later-line failure')
            return original_create(**kwargs)

        with patch('shop.services.OrderItem.objects.create', side_effect=fail_second):
            self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        self.product.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(self.second.stock, 1)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_invalid_checkout_and_foreign_token(self):
        self.add()
        data = self.checkout_data()
        self.assertEqual(
            self.client.post(reverse('checkout'), {**data, 'email': 'invalid', 'phone': 'abc'}).status_code, 400)
        self.assertEqual(self.client.post(reverse('checkout'), {**data, 'checkout_token': str(uuid4())}).status_code,
                         400)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_bkash_disabled_without_configuration_and_never_fakes_payment(self):
        self.add()
        data = self.checkout_data()
        data.update(payment_method='BKASH', bkash_number='01700000000', trx_id='ABC123')
        self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        self.store.bkash_number = '01711111111'
        self.store.bkash_account_type = 'merchant'
        self.store.bkash_account_confirmed = True
        self.store.bkash_manual_enabled = True
        self.store.bkash_manual_approved = True
        self.store.bkash_manual_instructions = 'Use Merchant Payment with the order reference.'
        self.store.bkash_manual_limit = 10000
        self.store.save()
        self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_status, 'pending')
        self.assertEqual(order.trx_id, '')  # Pre-order transaction claims are ignored.
        response = self.client.post(reverse('manual_payment_reference', args=[order.payment_attempt.pk]), {'reference': 'ABC123'})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'manual_review')
        self.assertEqual(order.trx_id, 'ABC123')

    def test_order_access_permissions(self):
        self.add()
        self.client.post(reverse('checkout'), self.checkout_data())
        order = Order.objects.get(user=self.user)
        for route in ['order_detail', 'order_success_with_id']:
            url = reverse(route, args=[order.pk])
            self.assertEqual(self.client.get(url).status_code, 200)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.user)

    def test_snapshots_survive_rename_and_deletion(self):
        self.add()
        self.client.post(reverse('checkout'), self.checkout_data())
        self.product.name = 'Changed name'
        self.product.save()
        self.product.delete()
        item = OrderItem.objects.get(order__user=self.user)
        self.assertEqual(item.product_name, 'Test phone')
        self.assertIsNone(item.product)
        self.assertEqual(item.price, Decimal('100'))

    def test_wishlist_privacy_and_post(self):
        url = reverse('toggle_wishlist', args=[self.product.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertTrue(Wishlist.objects.filter(user=self.user, product=self.product).exists())
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('wishlist')), 'Test phone')

    def test_search_filter_sort_pagination_and_missing_images(self):
        response = self.client.get(reverse('product_list'), {'q': 'Test phone', 'category': self.category.pk,
                                                             'brand': self.brand.pk, 'min_price': '90',
                                                             'max_price': '110', 'sort': 'price_asc'})
        self.assertEqual(list(response.context['products']), [self.product])
        response = self.client.get(reverse('product_list'), {'category': self.category.pk, 'sort': 'price_desc'})
        self.assertEqual([p.pk for p in response.context['products']][:2], [self.variable.pk, self.product.pk])
        for n in range(15):
            Product.objects.create(name=f'Extra {n}', category=self.category, price=1)
        response = self.client.get(reverse('product_list'), {'category': self.category.pk, 'page': 2})
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertLessEqual(len(response.context['products']), 12)
        self.assertEqual(self.client.get(reverse('ajax_products'), {'q': 'Test phone'}).json()['products'][0]['image'],
                         '')
        for price in ['NaN', 'Infinity', '-1', 'invalid']:
            self.assertTrue(self.client.get(reverse('product_list'), {'min_price': price}).context['filter_error'])

    def test_admin_sections_tabs_and_active_content(self):
        section = HomeSection.objects.create(title='Selected products')
        SectionProduct.objects.create(section=section, product=self.product)
        SectionProduct.objects.create(section=section, product=self.second)
        html = self.client.get(reverse('home_section', args=[section.pk]), {'category': self.child.pk}).json()['html']
        self.assertIn('Test phone', html)
        self.assertNotIn('Another phone', html)
        Banner.objects.create(title='Real promotion', product=self.product, link=f'/product/{self.product.pk}/')
        Offer.objects.create(title='Active offer', description='Details')
        Offer.objects.create(title='Hidden offer', description='Details', is_active=False)
        home = self.client.get('/')
        self.assertContains(home, 'Real promotion')
        self.assertContains(home, 'Active offer')
        self.assertNotContains(home, 'Hidden offer')

    def test_review_updates_and_validates(self):
        self.client.force_login(self.user)
        url = reverse('product_detail', args=[self.product.pk])
        self.client.post(url, {'rating': '5', 'comment': 'Good'})
        self.client.post(url, {'rating': '4', 'comment': 'Updated'})
        self.assertEqual(self.product.reviews.count(), 1)
        self.assertEqual(self.product.reviews.get().rating, 4)
        self.client.post(url, {'rating': '9', 'comment': 'Invalid'})
        self.assertEqual(self.product.reviews.get().rating, 4)

    def test_preorders_owned_by_requesting_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('preorder'), {'name': 'Customer', 'email': 'a@example.com',
                                                          'phone': '01700000000', 'address': 'Dhaka',
                                                          'product_name': 'A requested device',
                                                          'product_details': 'Details', 'user': self.other.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Preorder.objects.get().user, self.user)

    def test_admin_rejects_cycles_and_unsafe_links(self):
        self.category.parent = self.child
        with self.assertRaises(ValidationError):
            self.category.full_clean()
        with self.assertRaises(ValidationError):
            Banner(title='Unsafe', link='javascript:alert(1)').full_clean()

    def test_legacy_stock_is_not_falsely_advertised(self):
        legacy = Product.objects.create(name='Legacy product', category=self.category, price=10)
        self.assertEqual(legacy.availability, 'Availability confirmed with order')
        self.add(legacy)
        self.assertEqual(self.client.post(reverse('checkout'), self.checkout_data()).status_code, 302)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.stock)

    def test_from_price_excludes_unavailable_cheaper_variant(self):
        self.empty_variant.price = Decimal('90')
        self.empty_variant.save()
        self.assertEqual(self.variable.selling_price, Decimal('150'))
        response = self.client.get(reverse('product_list'), {'q': 'Variant phone', 'min_price': '140'})
        self.assertEqual(list(response.context['products']), [self.variable])

    def test_admin_content_screens_and_invalid_product_validation(self):
        staff = User.objects.create_superuser('store_admin', 'staff@example.com', 'test-password')
        self.client.force_login(staff)
        for name in ['banner', 'brand', 'category', 'homesection', 'product', 'offer', 'preorder', 'order']:
            self.assertEqual(self.client.get(f'/admin/shop/{name}/').status_code, 200)
        self.assertEqual(self.client.get(f'/admin/shop/product/{self.product.pk}/change/').status_code, 200)
        self.assertEqual(self.client.get('/admin/shop/storesettings/1/change/').status_code, 200)
        self.assertEqual(self.client.post('/admin/shop/product/add/', {'name': 'Missing price'}).status_code, 200)

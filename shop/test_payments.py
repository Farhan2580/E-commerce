from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from .models import (Category, Product, ProductVariant, Order, PaymentAttempt, StoreSettings,
                     Coupon, CouponRedemption)
from .payments import initiate, reconcile, retry_payment, GatewayUnavailable, safe_checkout_url
from .services import create_order


@override_settings(SSLCOMMERZ_STORE_ID='sandbox-test', SSLCOMMERZ_STORE_PASSWORD='test-secret',
                   SSLCOMMERZ_CARD_BRANDS=('visa', 'mastercard'),
                   SSLCOMMERZ_CARD_ENABLED=True, SSLCOMMERZ_BKASH_ENABLED=True,
                   PAYMENT_PUBLIC_URL='https://test.example')
class PaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('payer', email='payer@example.com')
        category = Category.objects.create(name='Payments test')
        self.product = Product.objects.create(name='Device', category=category, price=100, stock=5)
        store = StoreSettings.objects.get(pk=1)
        store.shipping_price = Decimal('25')
        store.save()
        self.client.force_login(self.user)

    def order(self, method='CARD', variant=None, coupon=''):
        token = str(uuid4())
        key = f'{self.product.pk}:{variant.pk}' if variant else str(self.product.pk)
        session = {'checkout_token': token, 'cart': {key: 2}}
        data = dict(checkout_token=token, full_name='Buyer', email='buyer@example.com',
                    address='Test address', phone='01700000000', payment_method=method, coupon_code=coupon,
                    total_price='0.01', trx_id='untrusted')
        order = create_order(self.user, session, data)
        return order, session, data

    def record(self, attempt, **changes):
        return dict(dict(APIConnect='DONE', status='VALID', val_id='validation-1',
                         tran_id=attempt.transaction_id, amount=str(attempt.amount), currency='BDT',
                         value_a=str(attempt.order_id), bank_tran_id='bank-1', risk_level='0'), **changes)

    def verify(self, attempt, **changes):
        record = self.record(attempt, **changes)
        with patch('shop.payments.api', side_effect=[{'APIConnect': 'DONE', 'element': [record]}, record]) as api:
            result = reconcile(attempt.pk)
        return result, api

    def test_pending_order_attempt_actual_total_and_stock_before_redirect(self):
        order, session, data = self.order()
        self.assertEqual(order.total_price, Decimal('225'))
        self.assertEqual(order.payment_status, 'pending')
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertEqual(order.payment_attempt.amount, order.total_price)
        self.assertEqual(len(order.payment_attempt.transaction_id), 30)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(create_order(self.user, session, data).pk, order.pk)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_hosted_session_is_created_once_and_reused(self):
        for method in ('CARD', 'ONLINE_BKASH'):
            order, _, _ = self.order(method)
            url = 'https://sandbox.sslcommerz.com/checkout/test'
            with patch('shop.payments.api', return_value=dict(status='SUCCESS', sessionkey='session', GatewayPageURL=url)) as api:
                self.assertEqual(initiate(order.payment_attempt.pk), url)
                self.assertEqual(initiate(order.payment_attempt.pk), url)
                self.assertEqual(api.call_count, 1)
                params = api.call_args.args[1]
                self.assertEqual(params['total_amount'], '225.00')
                self.assertEqual(params['value_a'], str(order.pk))
                self.assertEqual(params['multi_card_name'], 'bkash' if method == 'ONLINE_BKASH' else 'visacard,mastercard')

    def test_session_creation_timeout_is_not_retried(self):
        order, _, _ = self.order()
        with patch('shop.payments.api', side_effect=GatewayUnavailable) as api:
            self.assertEqual(initiate(order.payment_attempt.pk), '')
            self.assertEqual(initiate(order.payment_attempt.pk), '')
            self.assertEqual(api.call_count, 1)
        self.assertEqual(Order.objects.get(pk=order.pk).payment_status, 'pending')

    def test_reconciliation_during_initiation_does_not_lose_session(self):
        order, _, _ = self.order()
        attempt = order.payment_attempt
        with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': []}):
            self.assertEqual(reconcile(attempt.pk), 'pending')
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'created')
        url = 'https://sandbox.sslcommerz.com/checkout/test'

        def initiating_api(*args, **kwargs):
            with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': []}):
                self.assertEqual(reconcile(attempt.pk), 'pending')
            return dict(status='SUCCESS', sessionkey='session', GatewayPageURL=url)

        with patch('shop.payments.api', side_effect=initiating_api):
            self.assertEqual(initiate(attempt.pk), url)
        attempt.refresh_from_db()
        self.assertEqual(attempt.checkout_url, url)

    def test_server_validation_and_duplicate_callback_do_not_fulfill_twice(self):
        order, _, _ = self.order()
        result, api = self.verify(order.payment_attempt)
        self.assertEqual(result, 'paid')
        self.assertEqual(api.call_args_list[0].args[1]['tran_id'], order.payment_attempt.transaction_id)
        self.assertEqual(api.call_args_list[1].args[1]['val_id'], 'validation-1')
        with patch('shop.payments.api') as api:
            self.assertEqual(reconcile(order.payment_attempt.pk), 'paid')
            api.assert_not_called()
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status, 'received')
        self.assertEqual(order.status_events.filter(status='received').count(), 1)
        self.assertEqual(self.product.stock, 3)

    def test_mismatches_never_mark_paid(self):
        for field, value in [('amount', '0.01'), ('currency', 'USD'), ('tran_id', 'other'),
                             ('value_a', '999999'), ('amount', 'NaN')]:
            with self.subTest(field=field):
                order, _, _ = self.order()
                result, _ = self.verify(order.payment_attempt, **{field: value})
                self.assertEqual(result, 'review')
                order.refresh_from_db()
                self.assertEqual(order.status, 'awaiting_payment')
                self.product.stock = 5
                self.product.save()

    def test_validation_api_failure_keeps_pending(self):
        order, _, _ = self.order()
        record = self.record(order.payment_attempt)
        with patch('shop.payments.api', side_effect=[{'APIConnect': 'DONE', 'element': [record]}, {'status': 'INVALID'}]):
            self.assertEqual(reconcile(order.payment_attempt.pk), 'pending')

    def test_failed_and_cancelled_provider_results_release_stock_once(self):
        for status, expected in [('FAILED', 'failed'), ('CANCELLED', 'cancelled')]:
            order, _, _ = self.order()
            record = self.record(order.payment_attempt, status=status)
            with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': [record]}):
                self.assertEqual(reconcile(order.payment_attempt.pk), expected)
                self.assertEqual(reconcile(order.payment_attempt.pk), expected)
            order.refresh_from_db()
            self.product.refresh_from_db()
            self.assertEqual(order.status, 'cancelled')
            self.assertTrue(order.inventory_released)
            self.assertEqual(self.product.stock, 5)

    def test_spoofed_success_failure_and_cancellation_callbacks_are_ignored(self):
        order, _, _ = self.order()
        url = reverse('payment_ipn', args=[order.payment_attempt.pk])
        for status in ['VALID', 'FAILED', 'CANCELLED']:
            with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': []}):
                response = self.client.post(url, {'status': status, 'tran_id': 'fake', 'val_id': 'fake', 'amount': '225'})
            self.assertEqual(response.status_code, 200)
            order.refresh_from_db()
            self.assertEqual(order.payment_status, 'pending')
            self.assertFalse(order.inventory_released)

    def test_timeout_then_expiry_release_and_late_success_needs_review(self):
        order, _, _ = self.order()
        with patch('shop.payments.api', side_effect=GatewayUnavailable):
            self.assertEqual(reconcile(order.payment_attempt.pk), 'pending')
            PaymentAttempt.objects.filter(order=order).update(expires_at=timezone.now() - timedelta(seconds=1))
            self.assertEqual(reconcile(order.payment_attempt.pk), 'expired')
            self.assertEqual(reconcile(order.payment_attempt.pk), 'expired')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        result, _ = self.verify(order.payment_attempt)
        self.assertEqual(result, 'review')
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_variant_and_coupon_reservations_release(self):
        variant = ProductVariant.objects.create(product=self.product, name='Blue', price=150, stock=4)
        coupon = Coupon.objects.create(code='PAYTEST', kind='fixed', value=10, usage_limit=1)
        order, _, _ = self.order(variant=variant, coupon=coupon.code)
        self.assertEqual(order.total_price, 315)
        with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': [self.record(order.payment_attempt, status='FAILED')]}):
            reconcile(order.payment_attempt.pk)
        variant.refresh_from_db()
        self.product.refresh_from_db()
        coupon.refresh_from_db()
        self.assertEqual(variant.stock, 4)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(coupon.used_count, 0)
        self.assertFalse(CouponRedemption.objects.filter(order=order).exists())

    def test_risky_or_reused_bank_transaction_needs_review(self):
        order, _, _ = self.order()
        self.assertEqual(self.verify(order.payment_attempt, risk_level='1')[0], 'review')
        self.assertEqual(self.verify(order.payment_attempt)[0], 'paid')
        self.product.stock = 5
        self.product.save()
        another, _, _ = self.order()
        self.assertEqual(self.verify(another.payment_attempt)[0], 'review')

    @override_settings(SSLCOMMERZ_STORE_PASSWORD='')
    def test_unconfigured_methods_visible_but_not_selectable(self):
        session = self.client.session
        session['cart'] = {str(self.product.pk): 1}
        session.save()
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Card is currently unavailable')
        self.assertContains(response, 'bKash is currently unavailable')
        token = self.client.session['checkout_token']
        response = self.client.post(reverse('checkout'), dict(checkout_token=token, payment_method='CARD',
            full_name='Buyer', email='b@example.com', address='Dhaka', phone='01700000000'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_payment_refresh_and_start_require_owner_and_csrf(self):
        order, _, _ = self.order()
        other = User.objects.create_user('other-payer')
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(reverse('payment_start', args=[order.payment_attempt.pk])).status_code, 403)
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('payment_refresh', args=[order.payment_attempt.pk])).status_code, 404)

    def test_cod_and_manual_transfer_preserved(self):
        store = StoreSettings.objects.get(pk=1)
        store.bkash_number = '01700000000'
        store.bkash_account_type = 'merchant'
        store.bkash_account_confirmed = True
        store.bkash_manual_enabled = True
        store.bkash_manual_approved = True
        store.bkash_manual_instructions = 'Use Merchant Payment and include the order reference.'
        store.bkash_manual_limit = 10000
        store.save()
        for method, expected in [('COD', 'pending'), ('BKASH', 'pending')]:
            order, _, _ = self.order(method)
            self.assertEqual(order.payment_status, expected)
            self.assertEqual(PaymentAttempt.objects.filter(order=order).exists(), method == 'BKASH')

    def test_gateway_redirect_cannot_leave_sandbox(self):
        for url in ['https://evil.example/pay', 'http://sandbox.sslcommerz.com/pay',
                    'https://sandbox.sslcommerz.com.evil.example/pay', 'https://user:pass@sandbox.sslcommerz.com/pay']:
            self.assertFalse(safe_checkout_url(url))

    def test_out_of_range_online_total_rolls_back_inventory_and_order(self):
        self.product.price = 999999
        self.product.save()
        with self.assertRaises(ValidationError):
            self.order()
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def fail(self, attempt, status='FAILED'):
        with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': [self.record(attempt, status=status)]}):
            return reconcile(attempt.pk)

    def test_retry_uses_same_order_and_reserves_once_and_stale_failure_does_not_release(self):
        order, _, _ = self.order()
        old = order.payment_attempt
        self.fail(old)
        new = retry_payment(old.pk, self.user)
        self.assertNotEqual(new.transaction_id, old.transaction_id)
        self.assertEqual(new.order_id, old.order_id)
        self.assertEqual(retry_payment(old.pk, self.user).pk, new.pk)
        self.assertEqual(PaymentAttempt.objects.filter(order=order).count(), 2)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.fail(old)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')
        self.assertFalse(order.inventory_released)
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.verify(new)[0], 'paid')
        self.assertEqual(order.status_events.filter(status='received').count(), 1)

    def test_retry_rejects_pending_ambiguous_expired_and_review_states(self):
        order, _, _ = self.order()
        attempt = order.payment_attempt
        with self.assertRaises(ValidationError):
            retry_payment(attempt.pk, self.user)
        PaymentAttempt.objects.filter(pk=attempt.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        with patch('shop.payments.api', side_effect=GatewayUnavailable):
            reconcile(attempt.pk)
        with self.assertRaises(ValidationError):
            retry_payment(attempt.pk, self.user)
        self.assertEqual(PaymentAttempt.objects.filter(order=order).count(), 1)

    def test_retry_insufficient_stock_rolls_back_coupon_and_current_attempt(self):
        coupon = Coupon.objects.create(code='RETRY', kind='fixed', value=10, usage_limit=1)
        order, _, _ = self.order(coupon=coupon.code)
        old = order.payment_attempt
        self.fail(old)
        Product.objects.filter(pk=self.product.pk).update(stock=0)
        with self.assertRaises(ValidationError):
            retry_payment(old.pk, self.user)
        coupon.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(coupon.used_count, 0)
        self.assertTrue(old.is_current)
        self.assertEqual(order.payment_attempts.count(), 1)
        self.assertFalse(CouponRedemption.objects.filter(order=order).exists())

    def test_success_on_superseded_attempt_blocks_new_fulfillment(self):
        order, _, _ = self.order()
        old = order.payment_attempt
        self.fail(old)
        new = retry_payment(old.pk, self.user)
        self.assertEqual(self.verify(old)[0], 'review')
        with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': []}):
            self.assertEqual(reconcile(new.pk), 'review')
        self.assertEqual(initiate(new.pk), '')
        self.assertEqual(self.verify(new, bank_tran_id='bank-2')[0], 'review')
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'review')
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertFalse(order.status_events.filter(status='received').exists())

    def test_checkout_has_three_choices_and_preserves_shipping_on_invalid_post(self):
        session = self.client.session
        session['cart'] = {str(self.product.pk): 1}
        session.save()
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'class="gf-payment-card', count=3)
        self.assertContains(response, 'Place Order')
        token = self.client.session['checkout_token']
        data = dict(checkout_token=token, payment_method='CARD', full_name='Saved Buyer',
                    email='buyer@example.com', address='Saved address', phone='invalid')
        self.assertContains(self.client.post(reverse('checkout'), data), 'Saved Buyer', status_code=400)
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Saved Buyer')
        self.assertContains(response, 'Saved address')
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_cod_collection_requires_specific_staff_permission_and_is_idempotent(self):
        from django.contrib.auth.models import Permission
        from django.contrib.admin.models import LogEntry
        order, _, _ = self.order('COD')
        staff = User.objects.create_user('collector', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='change_order', content_type__app_label='shop'))
        self.client.force_login(staff)
        url = reverse('admin:shop_order_changelist')
        data = {'action': 'record_cod_collection', '_selected_action': str(order.pk)}
        self.client.post(url, data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')
        staff.user_permissions.add(Permission.objects.get(codename='record_cod_collection', content_type__app_label='shop'))
        self.client.post(url, data)
        self.client.post(url, data)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(LogEntry.objects.filter(object_id=str(order.pk), user=staff).count(), 1)

    def test_retry_endpoint_requires_owner_and_keeps_shipping(self):
        order, _, _ = self.order()
        old = order.payment_attempt
        self.fail(old, 'CANCEL')
        other = User.objects.create_user('retry-other')
        self.client.force_login(other)
        url = reverse('payment_retry', args=[old.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.user)
        record = self.record(old, status='CANCEL')
        with patch('shop.payments.api', side_effect=[{'APIConnect': 'DONE', 'element': [record]},
             {'status': 'SUCCESS', 'sessionkey': 'new', 'GatewayPageURL': 'https://sandbox.sslcommerz.com/checkout/new'}]):
            response = self.client.post(url)
        self.assertEqual(response.url, 'https://sandbox.sslcommerz.com/checkout/new')
        order.refresh_from_db()
        self.assertEqual(order.address, 'Test address')
        self.assertEqual(order.full_name, 'Buyer')

    def test_retry_rejected_if_provider_no_longer_confirms_failure(self):
        order, _, _ = self.order()
        old = order.payment_attempt
        self.fail(old)
        with patch('shop.payments.api', return_value={'APIConnect': 'DONE', 'element': []}):
            reconcile(old.pk)
        with self.assertRaises(ValidationError):
            retry_payment(old.pk, self.user)
        self.assertEqual(initiate(old.pk), '')
        self.assertEqual(order.payment_attempts.count(), 1)

    def test_retry_restores_valid_coupon_and_second_failure_releases_once(self):
        coupon = Coupon.objects.create(code='REPEAT', kind='fixed', value=10, usage_limit=1)
        order, _, _ = self.order(coupon=coupon.code)
        old = order.payment_attempt
        self.fail(old)
        new = retry_payment(old.pk, self.user)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)
        self.fail(old)
        self.fail(new)
        self.fail(new)
        coupon.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(coupon.used_count, 0)
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(CouponRedemption.objects.filter(order=order).exists())

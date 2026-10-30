from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Category, Product, StoreSettings, Order, PaymentAttempt, ManualPaymentClaim
from .services import create_order, enabled_payment_methods
from .manual_payments import submit_reference, review_reference
from .payments import reconcile, accepted_card_brands, method_ready


@override_settings(SSLCOMMERZ_STORE_ID='', SSLCOMMERZ_STORE_PASSWORD='', SSLCOMMERZ_CARD_BRANDS=())
class ManualPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manual-buyer')
        self.staff = User.objects.create_user('verifier', is_staff=True)
        category = Category.objects.create(name='Manual payment test')
        self.product = Product.objects.create(name='Test device', category=category, price=100, stock=5)
        self.store = StoreSettings.objects.get(pk=1)
        self.store.bkash_number = '01300972969'
        self.store.requested_settlement_account = '1082829510001'
        self.store.phone_verified = False  # Isolate receiving details from an independently verified contact phone.
        self.store.shipping_price = 25
        self.store.save()
        self.client.force_login(self.user)

    def configure(self, account_type='merchant'):
        self.store.bkash_account_type = account_type
        self.store.bkash_account_confirmed = True
        self.store.bkash_manual_enabled = True
        self.store.bkash_manual_approved = True
        self.store.bkash_manual_limit = 10000
        self.store.bkash_manual_instructions = 'Use Merchant Payment. Verify the business name and include the order reference.'
        self.store.save()

    def order(self):
        token = str(uuid4())
        return create_order(self.user, {'checkout_token': token, 'cart': {str(self.product.pk): 1}},
            dict(checkout_token=token, payment_method='BKASH', full_name='Buyer', email='b@example.com',
                 address='Dhaka', phone='01700000000'))

    def grant(self):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='shop',
            codename__in=['change_order', 'verify_manual_payment', 'view_manualpaymentclaim']))
        self.staff = User.objects.get(pk=self.staff.pk)

    def test_requested_numbers_do_not_enable_or_leak_destinations(self):
        # Keep the private receiver distinct from the explicitly public support
        # phone displayed in the footer; still assert no receiver leaks anywhere.
        self.store.bkash_number = '01711111111'
        self.store.save()
        self.assertFalse(self.store.manual_bkash_ready)
        self.assertNotIn('BKASH', dict(enabled_payment_methods(self.store)))
        session = self.client.session
        session['cart'] = {str(self.product.pk): 1}
        session.save()
        response = self.client.get(reverse('checkout'))
        self.assertNotContains(response, self.store.bkash_number)
        self.assertNotContains(response, self.store.requested_settlement_account)
        self.assertNotContains(response, 'sandbox')
        self.assertNotContains(response, 'Store Password')
        self.assertContains(response, 'bKash is currently unavailable')
        self.assertContains(response, 'Card is currently unavailable')

    def test_personal_account_cannot_enable_business_collection(self):
        self.configure('personal')
        self.assertFalse(self.store.manual_bkash_ready)
        with self.assertRaises(ValidationError):
            self.order()

    def test_approved_pra_uses_exact_instructions_not_send_money(self):
        self.configure('pra')
        order = self.order()
        self.assertEqual(order.payment_attempt.manual_receiver, self.store.bkash_number)
        response = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertContains(response, 'Use Merchant Payment')
        self.assertContains(response, 'GF' + str(order.pk))
        self.assertContains(response, '125.00')
        self.assertContains(response, 'Copy number')
        self.assertNotContains(response, self.store.requested_settlement_account)

    def test_claim_remains_unpaid_and_duplicate_submission_is_idempotent(self):
        self.configure()
        order = self.order()
        self.assertEqual(order.payment_status, 'pending')
        claim = submit_reference(order.payment_attempt.pk, self.user, 'aBC1234567')
        self.assertEqual(submit_reference(order.payment_attempt.pk, self.user, 'ABC1234567').pk, claim.pk)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'manual_review')
        self.assertEqual(order.get_payment_status_display(), 'Awaiting verification')
        self.assertEqual(order.status, 'awaiting_payment')
        self.assertEqual(claim.audit_events.count(), 1)
        with self.assertRaises(ValidationError):
            submit_reference(order.payment_attempt.pk, self.user, 'DIFFERENT123')

    def test_same_reference_cannot_pay_two_orders(self):
        self.configure()
        first, second = self.order(), self.order()
        submit_reference(first.payment_attempt.pk, self.user, 'UNIQUE1234')
        with self.assertRaises(ValidationError):
            submit_reference(second.payment_attempt.pk, self.user, 'UNIQUE1234')
        self.assertEqual(ManualPaymentClaim.objects.count(), 1)

    def test_numeric_pin_or_otp_is_not_saved_as_a_reference(self):
        self.configure()
        order = self.order()
        with self.assertRaises(ValidationError):
            submit_reference(order.payment_attempt.pk, self.user, '123456')
        self.assertFalse(ManualPaymentClaim.objects.exists())

    def test_manual_confirmation_requires_staff_permission_and_audit(self):
        self.configure()
        order = self.order()
        claim = submit_reference(order.payment_attempt.pk, self.user, 'CHECK12345')
        with self.assertRaises(PermissionDenied):
            review_reference(claim.pk, self.staff, 'confirmed', 'Checked actual receipt.')
        self.grant()
        review_reference(claim.pk, self.staff, 'confirmed', 'Merchant statement checked for recipient, BDT 125 and order reference.')
        review_reference(claim.pk, self.staff, 'confirmed', 'Same decision repeated.')
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status_events.filter(status='received').count(), 1)
        self.assertEqual(claim.audit_events.count(), 2)
        self.assertEqual(claim.audit_events.get(action='confirmed').actor, self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_staff_form_requires_all_merchant_record_checks(self):
        self.configure()
        self.grant()
        order = self.order()
        claim = submit_reference(order.payment_attempt.pk, self.user, 'FORM12345')
        self.client.force_login(self.staff)
        url = reverse('admin:shop_manualpaymentclaim_review', args=[claim.pk])
        response = self.client.post(url, {'decision': 'confirmed', 'note': 'A screenshot was supplied.'})
        self.assertContains(response, 'Complete every merchant-record check')
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'manual_review')

    def test_rejection_releases_once_and_cannot_be_overridden(self):
        self.configure()
        self.grant()
        order = self.order()
        claim = submit_reference(order.payment_attempt.pk, self.user, 'REJECT1234')
        review_reference(claim.pk, self.staff, 'rejected', 'No matching merchant receipt found.')
        review_reference(claim.pk, self.staff, 'rejected', 'Repeat rejection.')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        with self.assertRaises(ValidationError):
            review_reference(claim.pk, self.staff, 'confirmed', 'Attempt to override decision.')

    def test_abandonment_and_expired_claims_release_stock_without_fulfillment(self):
        self.configure()
        self.grant()
        order = self.order()
        attempt = order.payment_attempt
        claim = submit_reference(attempt.pk, self.user, 'LATE12345')
        PaymentAttempt.objects.filter(pk=attempt.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(reconcile(attempt.pk), 'review')
        self.assertEqual(reconcile(attempt.pk), 'review')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        with self.assertRaises(ValidationError):
            review_reference(claim.pk, self.staff, 'confirmed', 'Late receipt needs refund review.')

    def test_reference_endpoint_checks_owner(self):
        self.configure()
        order = self.order()
        other = User.objects.create_user('other-manual')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('manual_payment_reference', args=[order.payment_attempt.pk]), {'reference': 'TEST12345'}).status_code, 404)

    def test_manual_limit_is_checked_server_side_before_reservation(self):
        self.configure()
        self.store.bkash_manual_limit = Decimal('50')
        self.store.save()
        with self.assertRaises(ValidationError):
            self.order()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    @override_settings(SSLCOMMERZ_STORE_ID='test', SSLCOMMERZ_STORE_PASSWORD='test',
        SSLCOMMERZ_CARD_ENABLED=True, PAYMENT_PUBLIC_URL='https://test.example', SSLCOMMERZ_CARD_BRANDS=('visa',))
    def test_only_configured_card_brand_assets_are_shown(self):
        session = self.client.session
        session['cart'] = {str(self.product.pk): 1}
        session.save()
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'payment-brands/visa.svg')
        self.assertNotContains(response, 'payment-brands/mastercard.png')
        self.assertNotContains(response, 'all cards')
        with self.settings(SSLCOMMERZ_CARD_BRANDS=('unknown',)):
            self.assertEqual(accepted_card_brands(), [])
            self.assertFalse(method_ready('CARD'))

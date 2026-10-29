from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (BusinessLink, Category, FAQ, InformationPage, Order,
                     OrderStatusEvent, Product, ProductWarranty, StoreSettings, SupportRateLimit, SupportRequest)
from .services import create_order, enabled_payment_methods


class SupportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user('support_customer', 'customer@example.test', 'test-password')
        cls.other = User.objects.create_user('other_customer', 'other@example.test', 'test-password')
        cls.staff = User.objects.create_superuser('support_staff', 'staff@example.test', 'test-password')
        cls.category = Category.objects.create(name='Support test electronics')
        cls.product = Product.objects.create(name='Support test phone', category=cls.category, price=100, stock=3)
        cls.order = Order.objects.create(user=cls.customer, full_name='Private Customer', email='customer@example.test',
            address='Private delivery address', phone='01300972969', total_price=100,
            courier_name='Fixture Courier', tracking_number='FIXTURE-123', tracking_url='https://courier.example.test/FIXTURE-123')
        OrderStatusEvent.objects.create(order=cls.order, status='received')
        OrderStatusEvent.objects.create(order=cls.order, status='processing')

    def contact_data(self, client=None):
        client = client or self.client
        response = client.get(reverse('policy', args=['contact']))
        return {'name': 'Test Customer', 'phone': '01300972969', 'email': 'customer@example.test',
                'message': 'Please help with a product enquiry.', 'topic': 'contact', 'website': '',
                'form_token': response.context['support_form'].initial['form_token']}

    def test_seeded_routes_and_drafts_do_not_leak(self):
        self.assertEqual(InformationPage.objects.count(), 11)
        self.assertContains(self.client.get(reverse('policy', args=['contact'])), '01300972969')
        for slug in ['contact', 'faqs', 'payments']:
            self.assertEqual(self.client.get(reverse('policy', args=[slug])).status_code, 200)
        for slug in ['shipping', 'returns', 'privacy', 'terms', 'cookies', 'about', 'warranty']:
            page = InformationPage.objects.get(slug=slug)
            self.assertEqual(page.status, 'draft')
            self.assertEqual(self.client.get(reverse('policy', args=[slug])).status_code, 404)
            self.assertEqual(self.client.get(reverse('policy', args=[slug]), {'preview': '1'}).status_code, 404)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, '/information/privacy/')
        self.assertContains(response, reverse('order_history'))
        self.assertContains(response, reverse('wishlist'))
        self.client.force_login(self.staff)
        preview = self.client.get(reverse('policy', args=['privacy']), {'preview': '1'})
        self.assertContains(preview, 'Staff preview')
        self.assertContains(preview, 'password hashes')
        self.assertNotContains(preview, 'Owner/legal reviewer')

    def test_publication_validation_and_safe_plain_text(self):
        page = InformationPage.objects.get(slug='shipping')
        page.status = 'published'
        with self.assertRaises(ValidationError):
            page.full_clean()
        page.body_en = '<script>unsafeFixture()</script>Verified shipping text.'
        page.full_clean()
        page.save()
        store = StoreSettings.objects.get(pk=1)
        store.shipping_price = 75
        store.save()
        response = self.client.get(reverse('policy', args=['shipping']))
        self.assertContains(response, '75.00')
        self.assertContains(response, '&lt;script&gt;unsafeFixture()&lt;/script&gt;')
        self.assertNotContains(response, '<script>unsafeFixture()</script>')
        self.assertContains(self.client.get(reverse('home')), '/information/shipping/')
        page.status = 'draft'
        page.save()
        self.assertNotContains(self.client.get(reverse('home')), '/information/shipping/')

    def test_legacy_language_url_is_english_only_and_keeps_safe_return(self):
        self.assertEqual(self.client.get(reverse('support_language')).status_code, 405)
        self.client.post(reverse('support_language'), {'language': 'bn', 'next': '/information/contact/'})
        response = self.client.get(reverse('policy', args=['contact']))
        self.assertContains(response, 'Contact Us')
        self.assertEqual(response.context['document_language'], 'en')
        self.assertEqual(response.context['support_form'].fields['name'].label, 'Name')
        self.assertEqual(self.client.session['support_language'], 'en')
        self.assertNotContains(response, 'gf-language-switch')
        page = InformationPage.objects.get(slug='about')
        page.body_en = 'Verified English-only draft story.'
        page.body_bn = ''
        page.status = 'published'
        page.save()
        response = self.client.get(reverse('policy', args=['about']))
        self.assertContains(response, 'Verified English-only draft story.')
        self.assertFalse(response.context['translation_fallback'])
        response = self.client.post(reverse('support_language'), {'language': 'en', 'next': 'https://outside.example.test/'})
        self.assertEqual(response.url, '/information/contact/')
        self.assertEqual(self.client.post(reverse('support_language'), {'language': 'invalid'}).status_code, 400)

    def test_contact_saved_once_with_validation_and_csrf(self):
        url = reverse('policy', args=['contact'])
        data = self.contact_data()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        request = SupportRequest.objects.get()
        self.assertEqual(request.phone, '01300972969')
        self.assertEqual(request.status, 'new')
        self.assertIsNone(request.user)
        self.client.post(url, data)
        self.assertEqual(SupportRequest.objects.count(), 1)
        invalid = {**self.contact_data(), 'email': 'invalid', 'phone': 'x', 'message': 'short'}
        self.assertEqual(self.client.post(url, invalid).status_code, 400)
        self.assertEqual(SupportRequest.objects.count(), 1)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(url, data).status_code, 403)
        self.assertEqual(strict.post(reverse('support_language'), {'language': 'bn'}).status_code, 403)
        self.assertEqual(self.client.get('/admin/shop/supportrequest/').status_code, 302)

    def test_honeypot_token_binding_expiry_and_db_rate_limit(self):
        url = reverse('policy', args=['contact'])
        data = self.contact_data()
        self.assertEqual(self.client.post(url, {**data, 'website': 'spam.test'}).status_code, 400)
        other_client = Client()
        other_client.get(url)
        self.assertEqual(other_client.post(url, data).status_code, 400)
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 8000):
            self.assertEqual(self.client.post(url, data).status_code, 400)
        self.assertEqual(SupportRequest.objects.count(), 0)
        SupportRateLimit.objects.all().delete()
        for index in range(5):
            result = self.client.post(url, {**self.contact_data(), 'message': f'A valid support message number {index}.'}, HTTP_X_FORWARDED_FOR=f'10.0.0.{index}')
            self.assertEqual(result.status_code, 302)
        result = self.client.post(url, self.contact_data(), HTTP_X_FORWARDED_FOR='another-fake-ip')
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result['Retry-After'], '3600')
        self.assertEqual(SupportRequest.objects.count(), 5)
        self.assertTrue(all(row.key != '127.0.0.1' for row in SupportRateLimit.objects.all()))

    def test_verified_details_links_and_credentials_never_render(self):
        store = StoreSettings.objects.get(pk=1)
        store.address = 'Unverified fixture address'
        store.email = 'unverified@example.test'
        store.license_details_en = 'Unverified license fixture'
        store.save()
        BusinessLink.objects.create(kind='social', label_en='Unverified social fixture', url='https://social.example.test/', is_verified=False)
        BusinessLink.objects.create(kind='social', label_en='Unsafe fixture', url='javascript:unsafeFixture()', is_verified=True)
        response = self.client.get(reverse('policy', args=['contact']))
        for value in [store.address, store.email, store.license_details_en, 'Unverified social fixture', 'Unsafe fixture']:
            self.assertNotContains(response, value)
        store.address_verified = store.email_verified = store.license_verified = True
        store.save()
        response = self.client.get(reverse('policy', args=['contact']))
        self.assertContains(response, store.address)
        self.assertContains(response, store.license_details_en)
        link = BusinessLink(kind='messenger', label_en='Bad', url='https://secret:password@example.test/')
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_tracking_ownership_support_binding_and_courier(self):
        url = reverse('track_order_detail', args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('track_order'), {'order': self.order.pk, 'phone': self.order.phone}).status_code, 404)
        self.assertEqual(self.client.post(url, self.contact_data()).status_code, 404)
        self.client.force_login(self.customer)
        response = self.client.get(url)
        self.assertContains(response, 'FIXTURE-123')
        self.assertContains(response, 'Processing')
        self.assertContains(response, self.order.tracking_url)
        data = {**self.contact_data(), 'form_token': response.context['support_form'].initial['form_token']}
        self.client.post(url, data)
        support = SupportRequest.objects.get()
        self.assertEqual(support.order, self.order)
        self.assertEqual(support.user, self.customer)
        self.assertEqual(support.kind, 'order')
        # A signed contact form cannot be reused as an order-support form.
        self.assertEqual(self.client.post(url, self.contact_data()).status_code, 400)
        self.order.tracking_url = 'javascript:unsafeTracking()'
        self.order.save()
        self.assertNotContains(self.client.get(url), 'javascript:unsafeTracking()')

    def test_faq_publication_search_and_live_configuration(self):
        FAQ.objects.create(group='returns', question_en='Private unanswered fixture', status='draft')
        response = self.client.get(reverse('policy', args=['faqs']))
        self.assertNotContains(response, 'Private unanswered fixture')
        self.assertContains(response, '<details', html=False)
        store = StoreSettings.objects.get(pk=1)
        store.shipping_price = 67
        store.save()
        response = self.client.get(reverse('policy', args=['faqs']), {'q': '67.00'})
        self.assertContains(response, '67.00')
        self.assertNotContains(response, 'How do I place an order?')
        entry = FAQ(group='returns', question_en='No answer', status='published')
        with self.assertRaises(ValidationError):
            entry.full_clean()

    @override_settings(EMAIL_HOST_PASSWORD='NEVER_EXPOSE_SUPPORT_FIXTURE_SECRET')
    def test_payment_sources_match_checkout_and_reject_disabled_methods(self):
        url = reverse('policy', args=['payments'])
        self.assertContains(self.client.get(url), 'Cash on Delivery')
        self.assertNotContains(self.client.get(url), 'bKash — manual transfer')
        self.assertNotContains(self.client.get(url), 'NEVER_EXPOSE_SUPPORT_FIXTURE_SECRET')
        store = StoreSettings.objects.get(pk=1)
        store.cod_enabled = False
        store.bkash_number = '01300972969'
        store.bkash_account_type = 'merchant'
        store.bkash_account_confirmed = True
        store.bkash_manual_enabled = True
        store.bkash_manual_approved = True
        store.bkash_manual_instructions = 'Use Merchant Payment with the order reference.'
        store.bkash_manual_limit = 10000
        store.save()
        self.assertEqual(list(dict(enabled_payment_methods(store))), ['BKASH'])
        response = self.client.get(url)
        self.assertContains(response, 'bKash — manual transfer')
        self.assertNotContains(response, 'Cash on Delivery')
        self.client.force_login(self.customer)
        self.client.post(reverse('add_to_cart', args=[self.product.pk]))
        checkout = self.client.get(reverse('checkout'))
        self.assertEqual(list(dict(checkout.context['form'].fields['payment_method'].choices)), ['BKASH'])
        data = {'checkout_token': self.client.session['checkout_token'], 'payment_method': 'COD', 'full_name': 'Test',
                'email': 'test@example.test', 'phone': '01300972969', 'address': 'Test address'}
        self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        with self.assertRaises(ValidationError):
            create_order(self.customer, self.client.session, data)
        store.bkash_number = ''
        store.save()
        self.assertContains(self.client.get(url), 'No payment methods are currently enabled.')

    def test_cookie_inventory_and_warranty_publication(self):
        page = InformationPage.objects.get(slug='cookies')
        page.status = 'published'
        page.save()
        response = self.client.get(reverse('policy', args=['cookies']))
        for value in ['sessionid', 'csrftoken', 'gf-theme-v2', 'gf-shopping-change', 'fonts.googleapis.com']:
            self.assertContains(response, value)
        self.assertContains(response, 'No analytics or marketing scripts')
        warranty = ProductWarranty.objects.create(product=self.product, warranty_type='manufacturer', period_en='Fixture period', coverage_en='Fixture coverage', is_verified=False)
        self.assertNotContains(self.client.get(reverse('product_detail', args=[self.product.pk])), 'Fixture coverage')
        warranty.is_verified = True
        warranty.save()
        self.assertContains(self.client.get(reverse('product_detail', args=[self.product.pk])), 'Fixture coverage')
        page = InformationPage.objects.get(slug='warranty')
        page.body_en = 'Owner-approved fixture warranty introduction.'
        page.status = 'published'
        page.save()
        self.assertContains(self.client.get(reverse('policy', args=['warranty'])), 'Fixture coverage')

    def test_expired_rate_hash_cleanup_preserves_requests(self):
        self.client.post(reverse('policy', args=['contact']), self.contact_data())
        SupportRateLimit.objects.create(key='expired-fixture', expires_at=timezone.now() - timedelta(days=1))
        call_command('clear_support_limits', verbosity=0)
        self.assertFalse(SupportRateLimit.objects.filter(key='expired-fixture').exists())
        self.assertEqual(SupportRequest.objects.count(), 1)

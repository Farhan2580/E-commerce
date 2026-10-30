from django.test import TestCase, override_settings
from django.urls import reverse

from .models import InformationPage, StoreSettings, BusinessLink
from .support import footer_payment_badges


class FooterTests(TestCase):
    def test_columns_and_published_links(self):
        response = self.client.get(reverse('home'))
        for heading in ['Customer Care', 'Company', 'My Account']:
            self.assertContains(response, '<summary>' + heading + '</summary>')
        self.assertContains(response, 'Tech and everyday essentials.')
        self.assertContains(response, 'tel:01300972969')
        self.assertNotContains(response, '/information/privacy/')
        for slug, title in [('shipping', 'Shipping Policy'), ('returns', 'Returns &amp; Refund Policy'),
                            ('warranty', 'Warranty Policy'), ('about', 'About Us'),
                            ('terms', 'Terms &amp; Conditions'), ('privacy', 'Privacy Policy'), ('cookies', 'Cookie Policy')]:
            page = InformationPage.objects.get(slug=slug)
            page.status = 'published'
            page.body_en = 'Business-approved English content.'
            page.save()
            response = self.client.get(reverse('home'))
            self.assertContains(response, title)
            self.assertContains(response, reverse('policy', args=[slug]))
            self.assertEqual(self.client.get(reverse('policy', args=[slug])).status_code, 200)
        for route in ['profile', 'order_history']:
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)
        for route in ['offers', 'preorder', 'cart_view', 'product_list', 'track_order', 'wishlist']:
            self.assertIn(self.client.get(reverse(route)).status_code, [200, 302])

    def test_contact_and_social_visibility(self):
        store = StoreSettings.objects.get(pk=1)
        store.email = 'hidden@example.test'
        store.email_verified = False
        store.save()
        BusinessLink.objects.create(kind='social', label_en='Verified profile', url='https://example.test/profile', is_verified=True)
        BusinessLink.objects.create(kind='social', label_en='Unverified profile', url='https://example.test/hidden')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Verified profile')
        self.assertNotContains(response, 'Unverified profile')
        self.assertNotContains(response, 'hidden@example.test')

    @override_settings(SSLCOMMERZ_STORE_ID='fixture', SSLCOMMERZ_STORE_PASSWORD='fixture',
                       PAYMENT_PUBLIC_URL='https://shop.example.test', SSLCOMMERZ_CARD_ENABLED=True,
                       SSLCOMMERZ_CARD_BRANDS=('visa',), SSLCOMMERZ_BKASH_ENABLED=True)
    def test_only_enabled_brands_with_sandbox_labels(self):
        badges = footer_payment_badges(StoreSettings.objects.get(pk=1))
        self.assertEqual([badge['name'] for badge in badges], ['Cash on Delivery', 'bKash', 'Visa'])
        self.assertTrue(all(badge['test_only'] for badge in badges[1:]))
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Sandbox · test-only')
        self.assertContains(response, 'shop/payment-brands/visa.svg')
        self.assertNotContains(response, 'shop/payment-brands/mastercard.png')
        self.assertNotContains(response, 'Nagad')
        self.assertNotContains(response, 'Rocket')
        with override_settings(SSLCOMMERZ_CARD_BRANDS=(), SSLCOMMERZ_BKASH_ENABLED=False):
            self.assertEqual([b['name'] for b in footer_payment_badges(StoreSettings.objects.get(pk=1))], ['Cash on Delivery'])

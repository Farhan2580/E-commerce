from django.test import TestCase, override_settings
from django.urls import reverse

from .models import InformationPage, StoreSettings, BusinessLink, Outlet, FooterGroup, Category, Brand, HomeSection
from .support import footer_payment_badges


class FooterTests(TestCase):
    def test_outlets_directory_order_and_safe_links(self):
        Outlet.objects.create(name='Hidden outlet', address='Private', map_url='https://example.test/map')
        outlet = Outlet.objects.create(name='Published outlet', address='Verified address',
                                      map_url='https://example.test/map', visible=True)
        first = FooterGroup.objects.create(title='First group', position=0)
        second = FooterGroup.objects.create(title='Second group', position=1)
        FooterGroup.objects.create(title='Empty hidden group')
        category = Category.objects.create(name='Actual category')
        brand = Brand.objects.create(name='Actual brand')
        first.categories.add(category)
        second.brands.add(brand)
        draft = HomeSection.objects.create(title='Hidden collection', active=False)
        second.collections.add(draft)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'See All Outlets')
        self.assertNotContains(response, 'Hidden outlet')
        self.assertNotContains(response, 'Empty hidden group')
        self.assertNotContains(response, 'Hidden collection')
        groups = response.context['footer_directory']
        self.assertEqual([g['title'] for g in groups], ['First group', 'Second group'])
        self.assertEqual(groups[0]['links'][0]['url'], reverse('product_list') + f'?category={category.pk}')
        self.assertEqual(groups[1]['links'][0]['url'], reverse('product_list') + f'?brand={brand.pk}')
        for group in groups:
            self.assertEqual(self.client.get(group['links'][0]['url']).status_code, 200)
        self.assertContains(self.client.get(reverse('outlets')), outlet.address)
        self.assertNotContains(self.client.get(reverse('outlets')), 'Private')

    def test_whatsapp_apps_and_english_publication(self):
        BusinessLink.objects.create(kind='whatsapp', label_en='WhatsApp', url='https://wa.me/8801700000000', is_verified=True)
        BusinessLink.objects.create(kind='google_play', label_en='Get it on Google Play', url='https://play.google.com/store/apps/details?id=test', is_verified=True)
        BusinessLink.objects.create(kind='app_store', label_en='Hidden fake app', url='https://example.test/app', is_verified=True)
        page = InformationPage.objects.get(slug='privacy')
        page.status, page.body_en, page.body_bn = 'published', '', 'Only non-English content'
        page.save()
        page.sections.update(body_en='')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'https://wa.me/8801700000000')
        self.assertContains(response, 'Get it on Google Play')
        self.assertNotContains(response, 'Hidden fake app')
        self.assertNotIn(reverse('policy', args=['privacy']), [p['url'] for p in response.context['footer_policies']])

    def test_columns_and_published_links(self):
        response = self.client.get(reverse('home'))
        for heading in ['About and Support', 'Policy']:
            self.assertContains(response, '<summary>' + heading + '</summary>')
        self.assertContains(response, StoreSettings.objects.get(pk=1).tagline)
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
            from django.utils.html import escape
            self.assertContains(response, escape(page.title_en))
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

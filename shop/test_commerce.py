import json
import re
from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from .commerce import pc_build, order_progress
from .forms import ReviewForm
from .models import (Category, Product, ProductVariant, Order, OrderItem, DeliveryZone, PCComponent,
                     ProductQuestion, ProductWarranty, Review, StoreSettings, BusinessLink)
from .seo import safe_json_ld
from .services import cart_lines


class CommerceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Upgrade test catalog')
        cls.product = Product.objects.create(category=cls.category, name='Test product', price=200, stock=10)
        cls.user = User.objects.create_user('upgrade-buyer', 'buyer@example.com', 'test-password')

    def guest_data(self, client=None):
        client = client or self.client
        client.post(reverse('add_to_cart', args=[self.product.pk]), {'quantity': '1'})
        response = client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        return {'full_name': 'Guest Buyer', 'email': 'guest@example.com', 'address': 'House 12, Dhaka',
                'phone': '01700000000', 'payment_method': 'COD', 'checkout_token': client.session['checkout_token']}

    def test_guest_checkout_private_access_idempotency_and_no_account_created(self):
        users_before = User.objects.count()
        data = self.guest_data()
        self.assertContains(self.client.get(reverse('checkout')), 'Guest checkout')
        result = self.client.post(reverse('checkout'), data)
        order = Order.objects.get(checkout_token=data['checkout_token'])
        self.assertIsNone(order.user)
        self.assertRedirects(result, reverse('order_success_with_id', args=[order.pk]))
        self.assertEqual(User.objects.count(), users_before)
        self.client.post(reverse('checkout'), data)
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        outsider = Client()
        self.assertEqual(outsider.get(reverse('order_detail', args=[order.pk])).status_code, 302)
        outsider.force_login(self.user)
        self.assertEqual(outsider.get(reverse('order_detail', args=[order.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse('order_detail', args=[order.pk])), 'Guest order')

    def test_guest_cannot_replay_another_sessions_token(self):
        data = self.guest_data()
        self.client.post(reverse('checkout'), data)
        other = Client()
        other_data = self.guest_data(other)
        other_data['checkout_token'] = data['checkout_token']
        self.assertEqual(other.post(reverse('checkout'), other_data).status_code, 400)
        self.assertFalse(other.session.get('guest_order_ids'))
        self.assertEqual(Order.objects.count(), 1)

    @override_settings(SSLCOMMERZ_STORE_ID='test-only', SSLCOMMERZ_STORE_PASSWORD='test-only',
                       SSLCOMMERZ_CARD_BRANDS=('visa',), SSLCOMMERZ_CARD_ENABLED=True,
                       PAYMENT_PUBLIC_URL='https://test.example')
    def test_guest_hosted_payment_actions_require_the_owning_session(self):
        data = self.guest_data()
        data['payment_method'] = 'CARD'
        with patch('shop.payments.initiate', return_value='https://sandbox.sslcommerz.com/checkout/test'):
            response = self.client.post(reverse('checkout'), data)
        self.assertEqual(response['Location'], 'https://sandbox.sslcommerz.com/checkout/test')
        order = Order.objects.get(checkout_token=data['checkout_token'])
        attempt = order.payment_attempt
        self.assertIsNone(order.user_id)
        self.assertEqual(order.status, 'awaiting_payment')
        outsider = Client()
        for name in ['payment_start', 'payment_refresh', 'payment_retry']:
            self.assertEqual(outsider.post(reverse(name, args=[attempt.pk])).status_code, 404)
        with patch('shop.payment_views.reconcile') as reconcile:
            self.assertEqual(self.client.post(reverse('payment_refresh', args=[attempt.pk])).status_code, 302)
            reconcile.assert_called_once_with(attempt.pk)
        with patch('shop.payment_views.initiate', return_value='https://sandbox.sslcommerz.com/checkout/test'):
            self.assertEqual(self.client.post(reverse('payment_start', args=[attempt.pk]))['Location'], 'https://sandbox.sslcommerz.com/checkout/test')
        with patch('shop.payment_views.reconcile'), patch('shop.payment_views.retry_payment', return_value=attempt) as retry, patch('shop.payment_views.initiate', return_value=''):
            self.client.post(reverse('payment_retry', args=[attempt.pk]))
            retry.assert_called_once_with(attempt.pk, None)

    def test_guest_manual_reference_is_session_scoped_and_does_not_mark_paid(self):
        store = StoreSettings.objects.get(pk=1)
        store.bkash_number = '01700000000'
        store.bkash_account_type = 'merchant'
        store.bkash_account_confirmed = store.bkash_manual_enabled = store.bkash_manual_approved = True
        store.bkash_manual_instructions = 'Test-only approved business collection instructions.'
        store.bkash_manual_limit = 10000
        store.save()
        data = self.guest_data()
        data['payment_method'] = 'BKASH'
        self.client.post(reverse('checkout'), data)
        order = Order.objects.get(checkout_token=data['checkout_token'])
        url = reverse('manual_payment_reference', args=[order.payment_attempt.pk])
        self.assertEqual(Client().post(url, {'reference': 'ABC123456'}).status_code, 404)
        self.assertEqual(self.client.post(url, {'reference': 'ABC123456'}).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'manual_review')

    def test_guest_tracking_cannot_disclose_another_guest_order(self):
        data = self.guest_data()
        self.client.post(reverse('checkout'), data)
        order = Order.objects.get(checkout_token=data['checkout_token'])
        self.assertContains(self.client.get(reverse('track_order_detail', args=[order.pk])), f'#{order.pk}')
        other = Order.objects.create(user=None, full_name='Other guest', email='other@example.com',
                                    address='Private address', phone='01700000000', total_price=10)
        self.assertEqual(self.client.get(reverse('track_order_detail', args=[other.pk])).status_code, 404)

    def test_variant_structured_data_uses_each_variants_actual_price_and_stock(self):
        variant = ProductVariant.objects.create(product=self.product, name='Black', price=250, stock=0, color='Black')
        body = self.client.get(reverse('product_detail', args=[self.product.pk])).content.decode()
        data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)[1])
        self.assertEqual(data['@type'], 'ProductGroup')
        self.assertEqual(Decimal(data['hasVariant'][0]['offers']['price']), variant.price)
        self.assertEqual(data['hasVariant'][0]['offers']['availability'], 'https://schema.org/OutOfStock')

    def test_guest_order_is_claimed_only_from_current_session_after_signup(self):
        data = self.guest_data()
        self.client.post(reverse('checkout'), data)
        order = Order.objects.get(checkout_token=data['checkout_token'])
        unrelated = Order.objects.create(user=None, full_name='Other guest', email='guest@example.com',
                                        address='Dhaka', phone='01700000000', total_price=10)
        response = self.client.post(reverse('signup'), {'username': 'new-owner', 'password1': 'Example!Password123', 'password2': 'Example!Password123'})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        unrelated.refresh_from_db()
        self.assertEqual(order.user.username, 'new-owner')
        self.assertIsNone(unrelated.user_id)

    def test_delivery_quotes_preview_and_order_snapshot_use_same_charge(self):
        zone = DeliveryZone.objects.create(name='Test delivery area', shipping_price=80, min_days=2, max_days=4)
        quote = self.client.get(reverse('delivery_quote'), {'zone': zone.pk}).json()
        self.assertEqual(Decimal(quote['shipping']), Decimal('80'))
        data = self.guest_data()
        pending = self.client.get(reverse('checkout'))
        self.assertTrue(pending.context['shipping_pending'])
        self.assertEqual(pending.context['grand_total'], Decimal('200'))
        self.assertEqual(self.client.post(reverse('checkout'), data).status_code, 400)
        data.update(delivery_zone=str(zone.pk), action='preview')
        preview = self.client.post(reverse('checkout'), data)
        self.assertEqual(preview.context['grand_total'], Decimal('280'))
        self.assertFalse(Order.objects.exists())
        data.pop('action')
        data['shipping_price'] = '0'
        self.client.post(reverse('checkout'), data)
        order = Order.objects.get(checkout_token=data['checkout_token'])
        self.assertEqual(order.shipping_price, Decimal('80'))
        self.assertEqual(order.delivery_area, zone.name)
        self.assertEqual(order.delivery_estimate, zone.estimate)
        zone.name, zone.shipping_price = 'Renamed', 150
        zone.save()
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('280'))
        self.assertEqual(order.delivery_area, 'Test delivery area')

    def test_inactive_delivery_zone_is_rejected_and_days_validated(self):
        zone = DeliveryZone.objects.create(name='Closed area', shipping_price=50, min_days=3, max_days=2, active=False)
        with self.assertRaises(ValidationError):
            zone.full_clean()
        self.assertEqual(self.client.get(reverse('delivery_quote'), {'zone': zone.pk}).status_code, 400)
        self.assertEqual(self.client.get(reverse('delivery_quote'), {'zone': 'invalid'}).status_code, 400)

    def test_delivery_preview_does_not_validate_empty_contact_fields(self):
        zone = DeliveryZone.objects.create(name='Preview test area', shipping_price=60, min_days=1, max_days=3)
        self.guest_data()
        response = self.client.post(reverse('checkout'), {'action': 'preview', 'delivery_zone': zone.pk,
            'checkout_token': self.client.session['checkout_token'], 'payment_method': 'COD'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'This field is required.')
        self.assertEqual(response.context['grand_total'], Decimal('260'))
        self.assertFalse(Order.objects.exists())

    def test_order_stages_preserve_cancelled_and_awaiting_payment_statuses(self):
        for status in ['cancelled', 'awaiting_payment']:
            steps = order_progress(Order(status=status))
            self.assertFalse(any(step['current'] or step['complete'] for step in steps))
        steps = order_progress(Order(status='packed'))
        self.assertEqual([step['label'] for step in steps if step['current']], ['Packed'])
        self.assertEqual(sum(step['complete'] for step in steps), 3)

    def test_review_photo_preserves_verified_purchase_evidence(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.client.force_login(self.user)
            stream = BytesIO()
            Image.new('RGB', (30, 30), 'orange').save(stream, format='PNG')
            image = SimpleUploadedFile('review.png', stream.getvalue(), content_type='image/png')
            self.client.post(reverse('product_detail', args=[self.product.pk]), {'rating': '5', 'comment': 'A real product photo', 'image': image})
            review = Review.objects.get(user=self.user, product=self.product)
            self.assertTrue(review.image.storage.exists(review.image.name))
            response = self.client.get(reverse('product_detail', args=[self.product.pk]))
            self.assertNotContains(response, 'Verified purchase')
            order = Order.objects.create(user=self.user, full_name='Buyer', email=self.user.email, phone='01700000000', address='Dhaka',
                                         total_price=200, status='delivered', payment_status='paid')
            OrderItem.objects.create(order=order, product=self.product, product_name=self.product.name, quantity=1, price=200)
            self.assertContains(self.client.get(reverse('product_detail', args=[self.product.pk])), 'Verified purchase')
            self.assertFalse(ReviewForm({'rating': '5', 'comment': 'Invalid'}, {'image': SimpleUploadedFile('bad.svg', b'<svg/>', content_type='image/svg+xml')}).is_valid())

    def test_question_moderation_validation_and_rate_limit(self):
        self.client.force_login(self.user)
        url = reverse('ask_question', args=[self.product.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'question': 'Does this support my existing hardware?'})
        question = ProductQuestion.objects.get()
        self.assertFalse(question.is_published)
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertNotContains(response, question.question)
        self.client.post(url, {'question': 'Another question right away?'})
        self.assertEqual(ProductQuestion.objects.count(), 1)
        question.answer, question.is_published = 'Please share the model with our team.', True
        question.save()
        self.assertContains(self.client.get(reverse('product_detail', args=[self.product.pk])), question.answer)

    def test_warranty_summary_does_not_publish_unverified_terms(self):
        warranty = ProductWarranty.objects.create(product=self.product, warranty_type='seller', period_en='12 months',
                                                  replacement_terms='Test replacement terms', box_contents='Test box contents')
        url = reverse('product_detail', args=[self.product.pk])
        self.assertNotContains(self.client.get(url), warranty.replacement_terms)
        warranty.is_verified = True
        warranty.save()
        response = self.client.get(url)
        self.assertContains(response, warranty.replacement_terms)
        self.assertContains(response, warranty.box_contents)

    def test_structured_data_is_safe_and_omits_unknown_stock_and_fake_ratings(self):
        self.product.description = '</script><script>alert(1)</script>'
        self.product.stock = None
        self.product.save()
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        body = response.content.decode()
        encoded = re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)[1]
        data = json.loads(encoded)
        self.assertEqual(data['offers']['priceCurrency'], 'BDT')
        self.assertNotIn('availability', data['offers'])
        self.assertNotIn('aggregateRating', data)
        self.assertNotIn('</script>', encoded)
        self.assertEqual(json.loads(safe_json_ld({'name': '<test>&'}))['name'], '<test>&')

    def test_sitemap_and_robots_include_public_catalog_only(self):
        response = self.client.get(reverse('sitemap'))
        self.assertContains(response, reverse('product_detail', args=[self.product.pk]))
        self.assertNotContains(response, '/checkout/')
        self.assertContains(self.client.get(reverse('robots')), 'Disallow: /admin/')

    def test_owner_portrait_has_a_static_fallback_for_missing_cloud_media(self):
        BusinessLink.objects.create(kind='whatsapp', label_en='WhatsApp', url='https://wa.me/8801300972969',
                                    is_verified=True, image='business_profiles/farhan-whatsapp-portrait.png')
        self.assertContains(self.client.get(reverse('home')), 'data-image-fallback="/static/shop/support/farhan-whatsapp-portrait.png"')


class PCBuilderTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Builder test parts')
        self.selection = {}
        specifications = {
            'cpu': {'socket': 'AM5', 'integrated_graphics': True, 'power_watts': 65},
            'motherboard': {'socket': 'AM5', 'memory_type': 'DDR5', 'form_factor': 'ATX', 'supported_storage_interfaces': ['NVMe']},
            'ram': {'memory_type': 'DDR5'}, 'storage': {'storage_interface': 'NVMe'},
            'psu': {'power_watts': 650}, 'case': {'supported_form_factors': ['ATX']},
        }
        self.profiles = {}
        for kind, values in specifications.items():
            product = Product.objects.create(category=self.category, name='Test ' + kind, price=100, stock=2)
            self.profiles[kind] = PCComponent.objects.create(product=product, kind=kind, **values)
            self.selection[kind] = str(product.pk)

    def test_matching_build_uses_current_prices_and_adds_all_parts_once(self):
        quote = pc_build(self.selection)
        self.assertTrue(quote['can_add'])
        self.assertEqual(quote['total'], Decimal('600'))
        self.assertGreaterEqual(len(quote['checks']), 5)
        response = self.client.get(reverse('pc_builder'), self.selection)
        self.assertContains(response, 'Add build to bag')
        changed = self.profiles['cpu'].product
        changed.price = 200
        changed.save()
        self.client.post(reverse('pc_builder'), {**self.selection, 'total': '1'})
        self.assertEqual(len(self.client.session['cart']), 6)
        self.assertEqual(sum(line['subtotal'] for line in cart_lines(self.client.session)), Decimal('700'))

    def test_incompatible_socket_memory_case_storage_and_psu_block_cart(self):
        for kind, field, value in [('cpu', 'socket', 'LGA1700'), ('ram', 'memory_type', 'DDR4'),
                                   ('case', 'supported_form_factors', ['Mini-ITX']), ('storage', 'storage_interface', 'SATA'),
                                   ('psu', 'power_watts', 100)]:
            profile = self.profiles[kind]
            original = getattr(profile, field)
            setattr(profile, field, value)
            profile.save()
            quote = pc_build(self.selection)
            self.assertFalse(quote['can_add'], (kind, quote))
            self.assertEqual(self.client.post(reverse('pc_builder'), self.selection).status_code, 400)
            self.assertFalse(self.client.session.get('cart'))
            setattr(profile, field, original)
            profile.save()

    def test_missing_or_disabled_components_and_out_of_stock_do_not_mutate_cart(self):
        self.assertFalse(pc_build({})['can_add'])
        profile = self.profiles['cpu']
        profile.active = False
        profile.save()
        self.assertFalse(pc_build(self.selection)['can_add'])
        profile.active = True
        profile.save()
        product = self.profiles['ram'].product
        product.stock = 0
        product.save()
        self.assertEqual(self.client.post(reverse('pc_builder'), self.selection).status_code, 400)
        self.assertFalse(self.client.session.get('cart'))

    def test_unknown_specs_warn_instead_of_claiming_full_compatibility(self):
        cpu = self.profiles['cpu']
        cpu.socket = ''
        cpu.save()
        result = pc_build(self.selection)
        self.assertTrue(any('specifications need confirmation' in text for text in result['warnings']))
        self.assertNotIn('CPU socket matches', result['checks'])
        cpu.integrated_graphics = False
        cpu.save()
        self.assertFalse(pc_build(self.selection)['can_add'])

    def test_builder_variant_selection_and_stock_are_validated_server_side(self):
        product = self.profiles['ram'].product
        variant = ProductVariant.objects.create(product=product, name='16 GB', price=150, stock=1)
        self.assertFalse(pc_build(self.selection)['can_add'])
        self.selection['ram'] = f'{product.pk}:{variant.pk}'
        self.assertTrue(pc_build(self.selection)['can_add'])
        self.client.post(reverse('pc_builder'), self.selection)
        before = self.client.session['cart'].copy()
        self.assertEqual(self.client.post(reverse('pc_builder'), self.selection).status_code, 400)
        self.assertEqual(self.client.session['cart'], before)

    def test_builder_json_summary_and_post_require_csrf(self):
        response = self.client.get(reverse('pc_builder'), {**self.selection, 'format': 'json'})
        self.assertIn('Your build', response.json()['html'])
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('pc_builder'), self.selection).status_code, 403)

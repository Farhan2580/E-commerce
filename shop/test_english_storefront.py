from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .forms import SupportForm
from .models import Category, Product, InformationPage, InformationSection, FAQ, Order
from .services import settings_for_store
from .support import faq_answer, payment_cards


class EnglishStorefrontTests(TestCase):
    def test_payment_helpers_ignore_legacy_bangla_argument(self):
        store = settings_for_store()
        store.cod_enabled = True
        store.save()
        cards = payment_cards(store, 'bn')
        cod = next(card for card in cards if card['code'] == 'COD')
        self.assertEqual(cod['title'], 'Cash on Delivery')
        self.assertEqual(cod['instructions'], 'Select Cash on Delivery at checkout when it is enabled.')
        faq = FAQ(answer_source='payments')
        self.assertIn('Cash on Delivery: Select Cash on Delivery', faq_answer(faq, store, 'bn'))

    def setUp(self):
        self.user = User.objects.create_user('english-customer', email='customer@example.test')
        category = Category.objects.create(name='English navigation test')
        self.product = Product.objects.create(name='English checkout test', category=category, price=100, stock=5)
        session = self.client.session
        session['support_language'] = 'bn'
        session.save()
        self.client.cookies['django_language'] = 'bn'

    def test_saved_preferences_and_browser_language_do_not_select_bangla(self):
        for url in [reverse('home'), reverse('product_list'), reverse('product_detail', args=[self.product.pk]),
                    reverse('offers'), *[reverse('policy', args=[slug]) for slug in ['contact', 'faqs', 'payments']]]:
            with self.subTest(url=url):
                response = self.client.get(url, {'language': 'bn'}, HTTP_ACCEPT_LANGUAGE='bn-BD,bn')
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<html lang="en"')
                self.assertNotContains(response, 'gf-language-switch')
                self.assertNotContains(response, 'name="language"')
                self.assertEqual(response.context['support_language'], 'en')
        self.assertEqual(self.client.session['support_language'], 'en')

    def test_policy_faq_and_sections_use_english_and_preserve_translations(self):
        page = InformationPage.objects.get(slug='about')
        page.status = 'published'
        page.body_en = 'Original English policy content.'
        page.body_bn = 'সংরক্ষিত বাংলা নীতি'
        page.save()
        section = InformationSection.objects.create(page=page, heading_en='English heading',
            heading_bn='বাংলা শিরোনাম', body_en='Original English section.', body_bn='সংরক্ষিত বাংলা বিভাগ')
        faq = FAQ.objects.create(group='support', question_en='English question?', question_bn='বাংলা প্রশ্ন',
            answer_en='English answer.', answer_bn='সংরক্ষিত বাংলা উত্তর', status='published')
        response = self.client.get(reverse('policy', args=['about']))
        self.assertContains(response, page.body_en)
        self.assertContains(response, section.body_en)
        self.assertNotContains(response, page.body_bn)
        self.assertNotContains(response, section.body_bn)
        response = self.client.get(reverse('policy', args=['faqs']))
        self.assertContains(response, faq.question_en)
        self.assertContains(response, faq.answer_en)
        self.assertNotContains(response, faq.answer_bn)
        page.refresh_from_db()
        section.refresh_from_db()
        faq.refresh_from_db()
        self.assertEqual(page.body_bn, 'সংরক্ষিত বাংলা নীতি')
        self.assertEqual(section.body_bn, 'সংরক্ষিত বাংলা বিভাগ')
        self.assertEqual(faq.answer_bn, 'সংরক্ষিত বাংলা উত্তর')

    def test_bangla_only_policy_stays_reachable_without_bangla_fallback(self):
        page = InformationPage.objects.get(slug='privacy')
        page.body_en = ''
        page.body_bn = 'শুধুমাত্র সংরক্ষিত বাংলা বিষয়বস্তু'
        page.status = 'published'
        page.save()
        response = self.client.get(reverse('policy', args=['privacy']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'English content is not available yet.')
        self.assertNotContains(response, page.body_bn)
        page.refresh_from_db()
        self.assertEqual(page.body_bn, 'শুধুমাত্র সংরক্ষিত বাংলা বিষয়বস্তু')

    def test_support_form_legacy_language_argument_still_uses_english(self):
        form = SupportForm({'name': '', 'phone': 'wrong', 'email': 'wrong', 'message': 'short',
                            'form_token': 'invalid'}, nonce='test', language='bn')
        self.assertFalse(form.is_valid())
        self.assertEqual(form.fields['name'].label, 'Name')
        self.assertEqual(form.errors['name'][0], 'This field is required.')
        self.assertIn('Enter a valid phone number.', form.errors['phone'])
        self.assertIn('This form expired or belongs to another session.', form.errors['form_token'][0])

    def test_checkout_navigation_and_cod_work_with_old_bangla_preference(self):
        self.client.force_login(self.user)
        session = self.client.session
        session['cart'] = {str(self.product.pk): 1}
        session['support_language'] = 'bn'
        session.save()
        home = self.client.get(reverse('home'))
        self.assertContains(home, reverse('cart_view'))
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Cash on Delivery')
        self.assertContains(response, 'Choose a payment method')
        self.assertNotContains(response, 'gf-language-switch')
        data = {'checkout_token': self.client.session['checkout_token'], 'payment_method': 'COD',
                'full_name': 'English Customer', 'email': 'customer@example.test', 'phone': 'invalid',
                'address': 'Saved shipping address'}
        response = self.client.post(reverse('checkout'), data)
        self.assertContains(response, 'Enter a valid phone number.', status_code=400)
        data['phone'] = '01700000000'
        response = self.client.post(reverse('checkout'), data)
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_method, 'COD')
        self.assertEqual(order.payment_status, 'pending')
        self.assertEqual(order.address, data['address'])

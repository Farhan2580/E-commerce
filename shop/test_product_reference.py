from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import Brand, Category, Product, ProductVariant, ProductWarranty
from .product_presentation import option_groups


class ReferenceProductTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.brand = Brand.objects.create(name='Reference Brand', logo='brands/reference.png')
        category = Category.objects.create(name='Reference devices')
        cls.product = Product.objects.create(name='Reference phone', category=category, brand=cls.brand, price=100, stock=20)
        cls.black = ProductVariant.objects.create(product=cls.product, name='Black 128GB', color='Black', storage='128GB', sku='REF-B128', price=110, compare_at_price=150, stock=2)
        cls.white = ProductVariant.objects.create(product=cls.product, name='White 256GB', color='White', storage='256GB', sku='REF-W256', price=120, stock=0)

    def test_attributes_resolve_exact_variants_and_preselect_real_available_price(self):
        groups = option_groups(self.product.variants.all())
        self.assertEqual([group['field'] for group in groups], ['color', 'storage'])
        page = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(page.context['initial_variant'].pk, self.black.pk)
        self.assertContains(page, f'value="{self.black.pk}" selected')
        self.assertContains(page, 'data-option-field="color" data-option-value="Black"')
        self.assertContains(page, 'REF-B128')
        payload = page.context['variant_data']
        self.assertEqual(payload[1]['stock'], 0)
        self.assertEqual(payload[1]['storage'], '256GB')
        self.assertEqual(payload[0]['original'], '150.00')

    def test_ambiguous_or_missing_attributes_keep_exact_configuration_selector(self):
        ProductVariant.objects.create(product=self.product, name='Black 128GB other region', color='Black', storage='128GB', price=125, stock=1)
        self.assertEqual(option_groups(self.product.variants.all()), [])
        page = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertIsNone(page.context['initial_variant'])
        self.assertContains(page, 'data-variant-choice')
        self.assertNotContains(page, 'data-option-groups')
        self.assertEqual(option_groups([ProductVariant(name='Unnamed attributes')]), [])

    def test_uploaded_brand_logo_and_no_logo_fallback_follow_brand_record(self):
        url = reverse('product_detail', args=[self.product.pk])
        self.assertContains(self.client.get(url), f'src="{self.brand.logo.url}" alt="Reference Brand"')
        self.brand.logo = ''
        self.brand.save()
        page = self.client.get(url)
        self.assertNotContains(page, 'data-brand-logo')
        self.assertContains(page, '<span>Reference Brand</span>', html=True)

    def test_tabs_preserve_review_errors_and_include_only_verified_warranty(self):
        url = reverse('product_detail', args=[self.product.pk])
        page = self.client.get(url)
        self.assertNotContains(page, '<a href="#warranty">Warranty</a>', html=True)
        ProductWarranty.objects.create(product=self.product, warranty_type='seller', period_en='1 year', is_verified=True)
        self.assertContains(self.client.get(url), '<a href="#warranty">Warranty</a>', html=True)
        user = User.objects.create_user('reference-reviewer', password='test-password')
        self.client.force_login(user)
        page = self.client.post(url, {'rating': '0', 'comment': ''})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'data-default-tab="reviews"')
        self.assertTrue(page.context['form'].errors)

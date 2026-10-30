from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Brand, Category, NavigationItem, Product, ProductVariant


class CollectionPageTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Phones & Tablets')
        self.brand = Brand.objects.create(name='Apple')
        self.first = Product.objects.create(name='Actual device A', category=self.category, brand=self.brand,
            price=100, stock=1, specifications={'RAM': '8GB', 'Processor': 'M2'})
        self.second = Product.objects.create(name='Actual device B', category=self.category, brand=self.brand,
            price=200, stock=0, specifications={'RAM': '16GB', 'Processor': 'M3'})
        ProductVariant.objects.create(product=self.first, name='Black / 256GB', color='Black', storage='256GB', price=100, stock=1)
        ProductVariant.objects.create(product=self.first, name='White / 512GB', color='White', storage='512GB', price=120, stock=0)

    def page(self, **params):
        response = self.client.get(reverse('product_list'), {'brand': self.brand.pk, **params})
        self.assertEqual(response.status_code, 200)
        return response

    def ids(self, response):
        return [p.pk for p in response.context['products']]

    def test_all_thirteen_menu_targets_have_real_collection_pages(self):
        call_command('configure_primary_navigation', apply=True, verbosity=0)
        self.assertEqual(NavigationItem.objects.count(), 13)
        for item in NavigationItem.objects.all():
            params = {'brand': item.brand_id} if item.brand_id else {'category': item.category_id}
            response = self.client.get(reverse('product_list'), params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['collection']['label'], item.label)
        self.assertEqual(Product.objects.count(), 2)

    def test_actual_facet_options_and_same_variant_matching(self):
        response = self.page(option_color='Black', option_storage='256GB')
        self.assertEqual(self.ids(response), [self.first.pk])
        self.assertFalse(self.ids(self.page(option_color='Black', option_storage='512GB')))
        self.assertFalse(self.ids(self.page(option_storage='Invented')))
        self.assertFalse(self.ids(self.page(spec_unauthorized='Anything')))

    def test_specs_price_stock_and_sort_are_server_side(self):
        self.assertEqual(self.ids(self.page(spec_ram='16GB')), [self.second.pk])
        self.assertEqual(self.ids(self.page(spec_ram=['8GB', '16GB'], sort='price_desc')), [self.second.pk, self.first.pk])
        self.assertEqual(self.ids(self.page(availability='available')), [self.first.pk])
        self.assertEqual(self.ids(self.page(min_price='150')), [self.second.pk])
        self.assertContains(self.page(min_price='not-a-price'), 'Enter a valid non-negative price.')

    def test_content_is_escaped_and_unconfigured_facets_stay_hidden(self):
        NavigationItem.objects.create(label='Apple Store', brand=self.brand, page_title='<script>alert(1)</script>', introduction='<b>Owner text</b>')
        response = self.page()
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<b>Owner text</b>')
        self.assertNotIn('Warranty', [f['label'] for f in response.context['filter_facets']])

    def test_pagination_and_sort_keep_multi_select_filters(self):
        for index in range(13):
            Product.objects.create(name=f'Paginated device {index}', category=self.category, brand=self.brand,
                                   price=300 + index, specifications={'RAM': '8GB'})
        response = self.page(spec_ram=['8GB', '16GB'], sort='price_desc', language='bn')
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertIn('spec_ram=8GB&spec_ram=16GB', response.context['query_string'])
        self.assertEqual([v for k, v in response.context['sort_parameters'] if k == 'spec_ram'], ['8GB', '16GB'])
        self.assertNotContains(response, 'name="language"')

    def test_empty_category_has_no_fake_products_or_specs(self):
        empty = Category.objects.create(name='Empty collection')
        response = self.client.get(reverse('product_list'), {'category': empty.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertFalse(response.context['filter_facets'])
        self.assertContains(response, 'Browse the full catalog')

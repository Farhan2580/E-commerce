from django.test import TestCase
from django.urls import reverse
from .models import Category, Brand, Product, NavigationItem
from .context_processors import navigation_categories


class CategoryNavigationTests(TestCase):
    def test_configured_navigation_visibility_order_and_brand_destination(self):
        brand = Brand.objects.create(name='Apple test')
        category = Category.objects.create(name='Configured category')
        NavigationItem.objects.create(label='Second', category=category, position=2)
        NavigationItem.objects.create(label='Apple Store', brand=brand, position=0)
        NavigationItem.objects.create(label='Hidden option', category=category, visible=False)
        NavigationItem.objects.create(label='First', category=category, position=1)
        menu = navigation_categories()
        self.assertEqual([item.name for item in menu], ['Apple Store', 'First', 'Second'])
        self.assertEqual(menu[0].nav_url, reverse('product_list') + f'?brand={brand.pk}')
        for item in menu:
            self.assertEqual(self.client.get(item.nav_url).status_code, 200)

    def test_brands_belong_to_category_include_descendants_and_filter(self):
        phones = Category.objects.create(name='Test phones')
        child = Category.objects.create(name='Test smartphones', parent=phones)
        laptops = Category.objects.create(name='Test laptops')
        phone_brand = Brand.objects.create(name='Phone brand')
        laptop_brand = Brand.objects.create(name='Laptop brand')
        product = Product.objects.create(name='Actual phone', category=child, brand=phone_brand, price=100)
        Product.objects.create(name='Actual laptop', category=laptops, brand=laptop_brand, price=200)
        with self.assertNumQueries(4):
            categories = navigation_categories()
        group = next(c for c in categories if c.pk == phones.pk)
        self.assertEqual([b['name'] for b in group.nav_brands], ['Phone brand'])
        response = self.client.get(group.nav_brands[0]['url'])
        self.assertContains(response, product.name)
        self.assertNotContains(response, 'Actual laptop')
        html = self.client.get(reverse('home'))
        self.assertContains(html, 'Browse Test phones options')
        self.assertContains(html, 'Test phones brands')

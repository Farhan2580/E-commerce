from decimal import Decimal
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from .models import Category, Product, HomeSection, SectionProduct


class ProductCollectionTests(TestCase):
    def test_curated_collection_and_category_tabs_use_actual_products(self):
        first = Category.objects.create(name='Collection phones')
        second = Category.objects.create(name='Collection watches')
        phone = Product.objects.create(name='Actual phone', category=first, price=100)
        watch = Product.objects.create(name='Actual watch', category=second, price=50)
        unrelated = Product.objects.create(name='Not in this collection', category=first, price=200)
        section = HomeSection.objects.create(title='Test Collection')
        SectionProduct.objects.create(section=section, product=phone)
        SectionProduct.objects.create(section=section, product=watch)
        response = self.client.get(reverse('home_section', args=[section.pk]), {'category': first.pk})
        html = response.json()['html']
        self.assertIn(phone.name, html)
        self.assertNotIn(watch.name, html)
        self.assertNotIn(unrelated.name, html)
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'aria-controls="products-{section.pk}"')
        self.assertContains(response, 'Next products in Test Collection')

    def test_card_formats_real_prices_without_inventing_savings(self):
        category = Category.objects.create(name='Price formatting')
        product = Product.objects.create(name='Real device', category=category, price=Decimal('151000.25'))
        html = render_to_string('shop/includes/product_card.html', {'product': product})
        self.assertIn('151,000.25', html)
        self.assertNotIn('OFF', html)
        product.compare_at_price = Decimal('152000.50')
        html = render_to_string('shop/includes/product_card.html', {'product': product})
        self.assertIn('1,000.25 OFF', html)
        self.assertEqual(product.price, Decimal('151000.25'))

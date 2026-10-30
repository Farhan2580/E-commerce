"""Regression coverage; all records are created only in Django's test database."""
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from .admin import ProductAdminForm
from .forms import CheckoutForm
from .models import Category, Product, Review, Order, OrderItem


class CheckoutIdentityTests(TestCase):
    def test_name_and_address_require_meaningful_content(self):
        form = CheckoutForm()
        for value in ('x', '12345', '---'):
            form.cleaned_data = {'full_name': value}
            with self.assertRaisesMessage(ValidationError, 'full name'):
                form.clean_full_name()
        for value in ('x', '     ', '-----'):
            form.cleaned_data = {'address': value}
            with self.assertRaisesMessage(ValidationError, 'shipping address'):
                form.clean_address()
        form.cleaned_data = {'full_name': ' Buyer ', 'address': ' Dhaka '}
        self.assertEqual(form.clean_full_name(), 'Buyer')
        self.assertEqual(form.clean_address(), 'Dhaka')


class SpecificationEditorTests(TestCase):
    def test_flat_object_or_empty_only(self):
        form = ProductAdminForm()
        for value in ([], ['text'], {'': 'text'}, {'Nested': {}}, {'List': []}, {'Missing': None}):
            form.cleaned_data = {'specifications': value}
            with self.assertRaisesMessage(ValidationError, 'JSON object'):
                form.clean_specifications()
        for value in ({}, {'Model': 'Verified model', 'Ports': 2}, None):
            form.cleaned_data = {'specifications': value}
            self.assertEqual(form.clean_specifications(), value or {})


class VerifiedPurchaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reviewer')
        category = Category.objects.create(name='Test category')
        self.product = Product.objects.create(category=category, name='Test device', price=100)
        Review.objects.create(product=self.product, user=self.user, rating=4, comment='Actual review')
        self.order = Order.objects.create(user=self.user, full_name='Buyer', email='buyer@example.com',
            phone='01700000000', address='Dhaka', total_price=Decimal('100'), status='delivered')
        OrderItem.objects.create(order=self.order, product=self.product, quantity=1, price=100)

    def verified(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        return list(response.context['reviews'])[0].verified_purchase

    def test_requires_delivered_and_verified_paid_and_same_customer(self):
        self.assertFalse(self.verified())  # COD is not paid merely by delivery.
        self.order.payment_status = 'paid'
        self.order.save()
        self.assertTrue(self.verified())
        self.order.status = 'cancelled'
        self.order.save()
        self.assertFalse(self.verified())
        self.order.status = 'delivered'
        self.order.user = User.objects.create_user('different-buyer')
        self.order.save()
        self.assertFalse(self.verified())

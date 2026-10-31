from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from .admin_navigation import grouped_navigation
from .admin_site import StoreAdminSite
from .models import Category, Product, ProductVariant, Order, OrderItem, ServiceClaim


class AdminWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('workspace-admin', password='test-password')
        cls.staff = User.objects.create_user('workspace-staff', is_staff=True, password='test-password')
        cls.category = Category.objects.create(name='Workspace category')
        cls.low = Product.objects.create(name='Low product', category=cls.category, price=100, stock=2)
        cls.untracked = Product.objects.create(name='Untracked product', category=cls.category, price=100)
        cls.options = Product.objects.create(name='Option product', category=cls.category, price=100, stock=0)
        cls.variant = ProductVariant.objects.create(product=cls.options, name='Available', price=100, stock=20)
        cls.order = Order.objects.create(full_name='Buyer', email='buyer@example.test', address='Dhaka', phone='01700000000', total_price=100, status='received')
        cls.item = OrderItem.objects.create(order=cls.order, product=cls.low, product_name=cls.low.name, price=100, quantity=1)
        cls.claim = ServiceClaim.objects.create(order=cls.order, item=cls.item, kind='return', reason='Item requires review')

    def test_dashboard_uses_one_site_and_keeps_every_permitted_model_reachable(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:index'))
        self.assertIsInstance(admin.site._wrapped, StoreAdminSite)
        groups = response.context['store_admin_groups']
        names = [model['object_name'] for group in groups for model in group['models']]
        expected = [model['object_name'] for app in response.context['available_apps'] for model in app['models']]
        self.assertCountEqual(names, expected)
        self.assertEqual(len(names), len(set(names)))
        self.assertContains(response, 'GadgetFlow Admin')
        self.assertContains(response, 'Store operations')
        self.assertContains(response, reverse('admin:shop_product_add'))
        for stat in response.context['store_admin_stats']:
            self.assertEqual(self.client.get(stat['url']).status_code, 200)

    def test_dashboard_and_sidebar_do_not_expose_unassigned_sections_or_counts(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_category', content_type__app_label='shop'))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        names = [model['object_name'] for group in response.context['store_admin_groups'] for model in group['models']]
        self.assertEqual(names, ['Category'])
        self.assertFalse(response.context['store_admin_stats'])
        self.assertNotContains(response, reverse('catalog_transfer'))
        self.assertNotContains(response, reverse('store_dashboard'))
        self.assertNotContains(response, reverse('admin:shop_product_add'))
        self.assertEqual(self.client.get(reverse('admin:shop_product_changelist')).status_code, 403)
        page = self.client.get(reverse('admin:shop_category_changelist'))
        self.assertContains(page, 'Catalog')
        self.assertNotContains(page, 'Payments &amp; promotions')

    def test_add_only_staff_can_reach_their_add_form_without_extra_tools(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='add_brand', content_type__app_label='shop'))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin:index'))
        models = response.context['store_admin_groups'][0]['models']
        self.assertEqual(models[0]['url'], reverse('admin:shop_brand_add'))
        self.assertEqual(self.client.get(models[0]['url']).status_code, 200)

    def test_inventory_and_pending_filters_match_actionable_dashboard_counts(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('admin:index'))
        counts = {stat['label']: stat['value'] for stat in page.context['store_admin_stats']}
        self.assertEqual(counts['Low stock'], 1)
        self.assertEqual(counts['Pending orders'], 1)
        self.assertEqual(counts['Open service requests'], 1)
        page = self.client.get(reverse('admin:shop_product_changelist'), {'inventory': 'low'})
        self.assertEqual([p.pk for p in page.context['cl'].queryset], [self.low.pk])
        self.variant.stock = 0
        self.variant.save()
        page = self.client.get(reverse('admin:shop_product_changelist'), {'inventory': 'low'})
        self.assertSetEqual({p.pk for p in page.context['cl'].queryset}, {self.low.pk, self.options.pk})
        self.order.status = 'delivered'
        self.order.save()
        page = self.client.get(reverse('admin:shop_order_changelist'), {'fulfillment': 'pending'})
        self.assertFalse(page.context['cl'].queryset.exists())

    def test_connected_forms_render_and_do_not_remove_payment_guards(self):
        self.client.force_login(self.admin)
        for name, args, text in [
            ('admin:shop_product_change', [self.low.pk], '1. Product identity'),
            ('admin:shop_order_change', [self.order.pk], '4. Payment summary'),
            ('admin:shop_navigationitem_add', [], 'Connect a storefront menu item'),
            ('admin:shop_storesettings_change', [1], 'Store-wide configuration'),
            ('admin:shop_serviceclaim_change', [self.claim.pk], 'Progress visible to customer'),
        ]:
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, text)
        response = self.client.get(reverse('admin:shop_order_change', args=[self.order.pk]))
        self.assertNotContains(response, 'name="payment_status"')
        self.assertContains(response, 'name="status"')

    def test_product_editor_without_image_permission_has_a_valid_form(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='change_product', content_type__app_label='shop'))
        self.client.force_login(self.staff)
        page = self.client.get(reverse('admin:shop_product_change', args=[self.low.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('gallery_uploads', page.context['adminform'].form.fields)
        self.assertNotContains(page, reverse('admin:shop_category_changelist'))

    def test_unmapped_future_model_remains_available(self):
        groups = grouped_navigation([{'app_label': 'extension', 'models': [
            {'object_name': 'Tool', 'name': 'Tools', 'admin_url': '/admin/extension/tool/', 'perms': {'view': True}}]}])
        self.assertEqual(groups[0]['key'], 'other')
        self.assertEqual(groups[0]['models'][0]['url'], '/admin/extension/tool/')

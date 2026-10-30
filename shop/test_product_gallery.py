from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path
from PIL import Image
from django.contrib.auth.models import User, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Category, Product, ProductImage, ProductVariant


def photo(name, color='red'):
    data = BytesIO()
    Image.new('RGB', (32, 32), color).save(data, 'PNG')
    return SimpleUploadedFile(name, data.getvalue(), 'image/png')


@override_settings(ROOT_URLCONF='djangoProject13.development_urls')
class ProductGalleryTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        config = override_settings(MEDIA_ROOT=self.directory.name)
        config.enable()
        self.addCleanup(config.disable)
        self.category = Category.objects.create(name='Gallery test')
        self.product = Product.objects.create(name='Gallery device', category=self.category, price=100, stock=2)
        self.staff = User.objects.create_superuser('gallery-admin', 'admin@example.test', 'test-password')
        self.client.force_login(self.staff)

    def data(self, files):
        return {'name': self.product.name, 'category': self.category.pk, 'price': '100', 'stock': '2',
                'position': '0', 'specifications': '{}', 'gallery_uploads': files,
                'variants-TOTAL_FORMS': '0', 'variants-INITIAL_FORMS': '0',
                'gallery-TOTAL_FORMS': '0', 'gallery-INITIAL_FORMS': '0',
                'warranty-TOTAL_FORMS': '0', 'warranty-INITIAL_FORMS': '0', '_save': 'Save'}

    def test_admin_multi_upload_keeps_original_and_saves_valid_storage_images(self):
        old = ProductImage.objects.create(product=self.product, image=photo('original.png'), position=5)
        original = Path(old.image.path).read_bytes()
        response = self.client.post(reverse('admin:shop_product_change', args=[self.product.pk]),
                                    self.data([photo('front.png'), photo('back.png', 'blue')]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.product.gallery.count(), 3)
        self.assertEqual(list(self.product.gallery.values_list('position', flat=True)), [5, 6, 7])
        self.assertEqual(Path(old.image.path).read_bytes(), original)
        for image in self.product.gallery.all():
            with Image.open(image.image.path) as file:
                file.verify()
            response = self.client.get(image.image.url, REMOTE_ADDR='127.0.0.1')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response['Content-Type'].startswith('image/'))
            response.close()

    def test_one_invalid_file_prevents_partial_upload(self):
        response = self.client.post(reverse('admin:shop_product_change', args=[self.product.pk]),
            self.data([photo('valid.png'), SimpleUploadedFile('fake.png', b'not an image', 'image/png')]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('gallery_uploads', response.context['adminform'].form.errors)
        self.assertEqual(self.product.gallery.count(), 0)

    def test_product_permission_does_not_grant_gallery_upload_permission(self):
        restricted = User.objects.create_user('product-editor', password='test-password', is_staff=True)
        restricted.user_permissions.add(Permission.objects.get(codename='change_product'))
        self.client.force_login(restricted)
        response = self.client.get(reverse('admin:shop_product_change', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('gallery_uploads', response.context['adminform'].form.fields)

    def test_gallery_only_product_description_images_and_variant_images_are_separate(self):
        front = ProductImage.objects.create(product=self.product, image=photo('front.png'), alt='Front view')
        description = ProductImage.objects.create(product=self.product, image=photo('description.png'), purpose='description')
        variant = ProductVariant.objects.create(product=self.product, name='Blue', color='Blue', price=125, stock=1, image=photo('blue.png', 'blue'))
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        urls = [image['url'] for image in response.context['gallery_images']]
        self.assertEqual(urls, [front.image.url, variant.image.url])
        self.assertNotIn(description.image.url, urls)
        self.assertEqual(response.context['variant_data'][0]['image'], variant.image.url)
        self.assertContains(response, 'data-gallery-zoom')
        self.assertContains(response, 'gf-image-viewer')
        self.assertContains(response, description.image.url)

    def test_duplicate_references_do_not_duplicate_gallery_thumbnails(self):
        image = ProductImage.objects.create(product=self.product, image=photo('same.png'))
        self.product.image = image.image.name
        self.product.save(update_fields=['image'])
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(len(response.context['gallery_images']), 1)

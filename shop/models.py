from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from decimal import Decimal
from urllib.parse import urlsplit
import uuid


def validate_store_link(value):
    parts = urlsplit(value)
    if not ((value.startswith('/') and not value.startswith('//')) or
            (parts.scheme == 'https' and parts.netloc)):
        raise ValidationError('Use a local path starting with / or an https:// URL.')


def validate_public_https(value):
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise ValidationError('Use a public https:// URL without embedded credentials.')


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    image = models.ImageField(upload_to='categories/', blank=True)
    featured = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'name']

    def clean(self):
        seen = {self.pk} if self.pk else set()
        parent = self.parent
        while parent:
            if parent.pk in seen:
                raise ValidationError({'parent': 'Categories cannot contain a parent cycle.'})
            seen.add(parent.pk)
            parent = parent.parent

    def __str__(self):
        return self.name


class NavigationItem(models.Model):
    label = models.CharField(max_length=80)
    hero_image = models.ImageField(upload_to='collection_banners/', blank=True)
    page_title = models.CharField(max_length=160, blank=True)
    introduction = models.TextField(blank=True, help_text='Approved English collection introduction. No HTML.')
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT)
    brand = models.ForeignKey('Brand', null=True, blank=True, on_delete=models.PROTECT)
    visible = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def clean(self):
        if not self.category_id and not self.brand_id:
            raise ValidationError('Choose a category or brand for this menu link.')

    def __str__(self):
        return self.label


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True, help_text='Preserved legacy product logo.')
    brand = models.ForeignKey('Brand', blank=True, null=True, on_delete=models.SET_NULL, related_name='products')
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                           validators=[MinValueValidator(Decimal('0'))])
    stock = models.PositiveIntegerField(null=True, blank=True,
                                        help_text='Blank preserves legacy products with untracked stock. Set a quantity to enforce inventory.')
    featured = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    specifications = models.JSONField(default=dict, blank=True,
                                      help_text='An object of specification names and values.')

    def clean(self):
        if self.price is not None and self.price < 0:
            raise ValidationError({'price': 'Price cannot be negative.'})
        if self.price is not None and self.compare_at_price is not None and self.compare_at_price < self.price:
            raise ValidationError({'compare_at_price': 'Original price must be at least the selling price.'})
        if not isinstance(self.specifications, dict):
            raise ValidationError({'specifications': 'Enter a JSON object.'})

    @property
    def pricing_item(self):
        variants = list(self.variants.all())
        available = [variant for variant in variants if variant.stock > 0]
        return min(available or variants, key=lambda variant: variant.price) if variants else self

    @property
    def selling_price(self):
        return self.pricing_item.price

    @property
    def has_variants(self):
        return bool(self.variants.all())

    @property
    def discount_percent(self):
        item = self.pricing_item
        if not item.compare_at_price or item.compare_at_price <= item.price:
            return 0
        return round((item.compare_at_price - item.price) / item.compare_at_price * 100)

    @property
    def display_original_price(self):
        return self.pricing_item.compare_at_price

    @property
    def discount_amount(self):
        item = self.pricing_item
        return max((item.compare_at_price or item.price) - item.price, Decimal('0'))

    @property
    def availability(self):
        variants = list(self.variants.all())
        if variants:
            return 'In stock' if any(v.stock > 0 for v in variants) else 'Out of stock'
        return 'Availability confirmed with order' if self.stock is None else (
            'In stock' if self.stock > 0 else 'Out of stock')

    @property
    def can_purchase(self):
        return self.availability != 'Out of stock'

    def __str__(self):
        return self.name


class Order(models.Model):
    class Meta:
        permissions = [('record_cod_collection', 'Can record cash on delivery collection'),
                       ('verify_manual_payment', 'Can verify manual payment against merchant records')]

    @property
    def payment_attempt(self):
        return self.payment_attempts.filter(is_current=True).first()

    inventory_released = models.BooleanField(default=False, editable=False)
    courier_name = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=150, blank=True)
    tracking_url = models.URLField(max_length=500, blank=True, validators=[validate_public_https])
    STATUS_CHOICES = [('awaiting_payment', 'Awaiting payment'), ('received', 'Received'), ('processing', 'Processing'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    coupon_code = models.CharField(max_length=40, blank=True)
    coupon_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    address = models.TextField()
    phone = models.CharField(max_length=20)
    total_price = models.DecimalField(max_digits=14, decimal_places=2)
    date_ordered = models.DateTimeField(auto_now_add=True)

    # পেমেন্ট অপশনগুলো আপডেট করা হয়েছে
    PAYMENT_CHOICES = [
        ('CARD', 'Card (hosted checkout)'),
        ('ONLINE_BKASH', 'bKash (hosted checkout)'),
        ('COD', 'Cash on Delivery'),
        ('BKASH', 'bKash'),
    ]
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='COD')

    # বিকাশ পেমেন্টের জন্য নতুন এই দুটি ফিল্ড অবশ্যই লাগবে
    bkash_number = models.CharField(max_length=15, null=True, blank=True)
    trx_id = models.CharField(max_length=50, null=True, blank=True)
    checkout_token = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    savings = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Unpaid / pending'),
                                                                                 ('manual_review',
                                                                                  'Awaiting verification'),
                                                                                 ('paid', 'Verified paid'),
                                                                                 ('failed', 'Payment failed'),
                                                                                 ('cancelled', 'Payment cancelled'),
                                                                                 ('expired', 'Payment expired'),
                                                                                 ('review', 'Payment needs reconciliation')])

    def __str__(self):
        return f"Order #{self.id} by {self.user.username}"

    def clean(self):
        if self.tracking_url and not (self.courier_name and self.tracking_number):
            raise ValidationError({'tracking_url': 'Assign a courier name and tracking number before adding a tracking link.'})

    @property
    def public_tracking_url(self):
        if not (self.courier_name and self.tracking_number):
            return ''
        try:
            validate_public_https(self.tracking_url)
            return self.tracking_url
        except ValidationError:
            return ''


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    product_name = models.CharField(max_length=200, blank=True)
    variant_name = models.CharField(max_length=200, blank=True)
    sku = models.CharField(max_length=100, blank=True)

    @property
    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product_name or (self.product.name if self.product else 'Deleted product')} (x{self.quantity})"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} - {self.rating}★ by {self.user.username}"


class Offer(models.Model):
    position = models.PositiveIntegerField(default=0, help_text='Lower values appear first; equal positions are ordered by ID.')
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='offers/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    products = models.ManyToManyField(Product, blank=True, related_name='offers')
    exclusive = models.BooleanField(default=False)
    link = models.CharField(max_length=500, blank=True, validators=[validate_store_link])

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.title

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'End must be after the start.'})


class Preorder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    product_name = models.CharField(max_length=255)
    product_details = models.TextField()
    image = models.ImageField(upload_to='preorder_images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Preorder: {self.product_name} by {self.name}"


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to='brands/', blank=True)
    featured = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'name']

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    image = models.ImageField(upload_to='variant_images/', blank=True, help_text='Optional actual option image; cart falls back to the product image.')
    color = models.CharField(max_length=60, blank=True)
    storage = models.CharField(max_length=60, blank=True)
    size = models.CharField(max_length=60, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=200, help_text='For example: Black / 256GB')
    sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                           validators=[MinValueValidator(Decimal('0'))])
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['product', 'name'], name='unique_product_variant')]

    def clean(self):
        if self.price is not None and self.compare_at_price is not None and self.compare_at_price < self.price:
            raise ValidationError({'compare_at_price': 'Original price must be at least the selling price.'})

    def __str__(self):
        return f'{self.product.name} — {self.name}'

    @property
    def option_label(self):
        attributes = ' / '.join(value for value in [self.color, self.storage, self.size] if value)
        return f'{self.name} ({attributes})' if attributes else self.name


class ProductImage(models.Model):
    purpose = models.CharField(max_length=20, default='gallery', choices=[('gallery', 'Product gallery'), ('description', 'Description image')])
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='product_gallery/')
    alt = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']


class Banner(models.Model):
    title = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    image = models.ImageField(upload_to='banners/', blank=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    link = models.CharField(max_length=500, default='/products/', validators=[validate_store_link])
    button_label = models.CharField(max_length=40, default='Shop now')
    active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.title


class HomeSection(models.Model):
    title = models.CharField(max_length=150)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    products = models.ManyToManyField(Product, through='SectionProduct', blank=True)
    active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.title


class SectionProduct(models.Model):
    section = models.ForeignKey(HomeSection, on_delete=models.CASCADE, related_name='placements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']
        constraints = [models.UniqueConstraint(fields=['section', 'product'], name='unique_section_product')]


class StoreSettings(models.Model):
    bkash_account_type = models.CharField(max_length=20, default='unconfirmed', choices=[
        ('unconfirmed', 'Not confirmed'), ('merchant', 'Merchant'), ('pra', 'Personal Retail Account'), ('personal', 'Personal')])
    bkash_account_confirmed = models.BooleanField(default=False, help_text='Staff verified ownership and account type with bKash.')
    bkash_manual_enabled = models.BooleanField(default=False)
    bkash_manual_approved = models.BooleanField(default=False, help_text='Provider approved this account for receiving business payments using the instructions below.')
    bkash_manual_instructions = models.TextField(blank=True, help_text='Exact provider-approved Merchant Payment instructions. Never substitute Send Money or request a PIN/OTP.')
    bkash_manual_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))], help_text='Confirmed per-payment limit. Zero keeps manual payments unavailable; staff must monitor aggregate account limits.')
    requested_settlement_account = models.CharField(max_length=40, blank=True, help_text='Requested destination only; never passed from checkout to the provider.')
    settlement_bank_name = models.CharField(max_length=150, blank=True)
    settlement_account_holder = models.CharField(max_length=150, blank=True)
    settlement_branch = models.CharField(max_length=150, blank=True)
    settlement_routing_number = models.CharField(max_length=30, blank=True)
    settlement_provider_approved = models.BooleanField(default=False, help_text='Staff record of provider approval; does not configure settlement at the provider.')

    @property
    def manual_bkash_ready(self):
        import re
        return bool(self.bkash_manual_enabled and self.bkash_account_confirmed
                    and self.bkash_manual_approved and self.bkash_account_type in {'merchant', 'pra'}
                    and re.fullmatch(r'01\d{9}', self.bkash_number)
                    and self.bkash_manual_instructions.strip() and self.bkash_manual_limit > 0)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    address_bn = models.TextField(blank=True)
    support_hours_en = models.CharField(max_length=250, blank=True)
    support_hours_bn = models.CharField(max_length=250, blank=True)
    license_details_en = models.TextField(blank=True)
    license_details_bn = models.TextField(blank=True)
    license_verified = models.BooleanField(default=False)
    cod_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    name = models.CharField(max_length=100, default='GadgetFlow')
    tagline = models.CharField(max_length=250,
                               default='Your destination for tech and everyday essentials in Bangladesh.')
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    shipping_price = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         validators=[MinValueValidator(Decimal('0'))])
    bkash_number = models.CharField(max_length=20, blank=True,
                                    help_text='Requested receiving number only. Account type and business collection approval must be confirmed separately.')
    privacy_policy = models.TextField(blank=True)
    returns_policy = models.TextField(blank=True)
    shipping_policy = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return 'GadgetFlow business settings'


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='unique_wishlist_product')]


class Coupon(models.Model):
    code = models.CharField(max_length=40, unique=True)
    active = models.BooleanField(default=True)
    kind = models.CharField(max_length=10, choices=[('percent', 'Percentage'), ('fixed', 'Fixed amount')])
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    minimum_order = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text='Blank means no global limit.')
    per_customer_limit = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    used_count = models.PositiveIntegerField(default=0, editable=False)
    products = models.ManyToManyField(Product, blank=True, help_text='Blank applies to the whole catalog.')
    categories = models.ManyToManyField(Category, blank=True, help_text='Exact categories; select children explicitly. Combined with products using OR.')
    customers = models.ManyToManyField(User, blank=True, help_text='Blank allows every signed-in customer.')

    def clean(self):
        self.code = self.code.strip().upper()
        if not self.code or any(character.isspace() for character in self.code):
            raise ValidationError({'code': 'Use a code without spaces.'})
        if self.kind == 'percent' and self.value is not None and self.value > 100:
            raise ValidationError({'value': 'Percentage cannot exceed 100.'})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'End must be after the start.'})

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name='redemptions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class SavedAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=60, default='Home')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.TextField(max_length=2000)

    def __str__(self):
        return f'{self.user.username} / {self.label}'


class OrderStatusEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_events')
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class StockAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stock_alerts')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.CASCADE)
    email = models.EmailField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], condition=models.Q(variant__isnull=True), name='unique_product_stock_alert'),
            models.UniqueConstraint(fields=['user', 'variant'], condition=models.Q(variant__isnull=False), name='unique_variant_stock_alert'),
        ]

    def clean(self):
        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError({'variant': 'Variant must belong to the product.'})


class InformationPage(models.Model):
    SLUGS = [('contact', 'Contact Us'), ('tracking', 'Track Your Order'), ('faqs', 'FAQs'),
             ('shipping', 'Shipping & Delivery'), ('returns', 'Returns & Refunds'),
             ('terms', 'Terms & Conditions'), ('privacy', 'Privacy Policy'),
             ('payments', 'Payment Methods'), ('cookies', 'Cookie Policy'),
             ('about', 'About Us'), ('warranty', 'Warranty & Exchange'),
             ('exchange', 'Exchange Policy'), ('preorder-policy', 'Preorder Policy'),
             ('refund', 'Refund Policy'), ('return', 'Return Policy'),
             ('corporate', 'Corporate'), ('blog', 'Blog'), ('press', 'Press Coverage'), ('careers', 'Careers')]
    slug = models.SlugField(unique=True, choices=SLUGS)
    title_en = models.CharField(max_length=160)
    title_bn = models.CharField(max_length=160, blank=True)
    body_en = models.TextField(blank=True, help_text='Plain text only; HTML is escaped.')
    body_bn = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=[('draft', 'Draft'), ('published', 'Published')], default='draft')
    footer_group = models.CharField(max_length=20, choices=[('care', 'Customer Care'), ('policies', 'Policies'), ('company', 'Company / Account')])
    position = models.PositiveIntegerField(default=0)
    editorial_notes = models.TextField(blank=True, help_text='Private business decisions/review checklist. Never rendered publicly.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'pk']

    def clean(self):
        operational = {'contact', 'tracking', 'faqs', 'payments'}
        if self.status == 'published' and self.slug not in operational and not (self.body_en.strip() or self.body_bn.strip()):
            has_sections = self.pk and self.sections.exclude(body_en='', body_bn='').exists()
            if not has_sections:
                raise ValidationError({'status': 'Save substantive page/section content before publishing. Missing policies must remain drafts.'})

    def __str__(self):
        return self.title_en


class InformationSection(models.Model):
    page = models.ForeignKey(InformationPage, on_delete=models.CASCADE, related_name='sections')
    heading_en = models.CharField(max_length=180)
    heading_bn = models.CharField(max_length=180, blank=True)
    body_en = models.TextField(blank=True)
    body_bn = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'pk']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.utils import timezone
        InformationPage.objects.filter(pk=self.page_id).update(updated_at=timezone.now())


class FAQ(models.Model):
    GROUPS = [('ordering', 'Ordering'), ('payments', 'Payments'), ('delivery', 'Delivery'),
              ('cancellation', 'Cancellation'), ('returns', 'Returns'), ('authenticity', 'Authenticity'),
              ('cod', 'Cash on delivery'), ('tracking', 'Tracking'), ('support', 'Support')]
    group = models.CharField(max_length=20, choices=GROUPS)
    question_en = models.CharField(max_length=300)
    question_bn = models.CharField(max_length=300, blank=True)
    answer_en = models.TextField(blank=True)
    answer_bn = models.TextField(blank=True)
    answer_source = models.CharField(max_length=20, default='text', choices=[('text', 'Editable text'), ('payments', 'Live enabled payments'), ('shipping', 'Live shipping charge'), ('tracking', 'Owner-only tracking'), ('support', 'Verified support contact')])
    status = models.CharField(max_length=12, choices=[('draft', 'Draft'), ('published', 'Published')], default='draft')
    position = models.PositiveIntegerField(default=0)
    editorial_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group', 'position', 'pk']

    def clean(self):
        if self.status == 'published' and self.answer_source == 'text' and not (self.answer_en.strip() or self.answer_bn.strip()):
            raise ValidationError({'status': 'Enter an answer before publishing.'})

    def __str__(self):
        return self.question_en


class BusinessLink(models.Model):
    image = models.ImageField(upload_to='business_profiles/', blank=True, help_text='Optional real support contact portrait for the WhatsApp shortcut.')
    kind = models.CharField(max_length=20, choices=[('whatsapp', 'WhatsApp'), ('messenger', 'Messenger'), ('map', 'Map'), ('social', 'Social profile'), ('app_store', 'App Store'), ('google_play', 'Google Play')])
    label_en = models.CharField(max_length=100)
    label_bn = models.CharField(max_length=100, blank=True)
    url = models.URLField(max_length=500, validators=[validate_public_https])
    is_verified = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.label_en


class Outlet(models.Model):
    name = models.CharField(max_length=120)
    address = models.TextField()
    hours = models.CharField(max_length=200, blank=True)
    map_url = models.URLField(max_length=500, validators=[validate_public_https])
    visible = models.BooleanField(default=False, help_text='Publish only verified outlet information.')
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.name


class FooterGroup(models.Model):
    title = models.CharField(max_length=100)
    visible = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    categories = models.ManyToManyField(Category, blank=True)
    brands = models.ManyToManyField(Brand, blank=True)
    collections = models.ManyToManyField(HomeSection, blank=True, help_text='Explicitly curated collections, including Trending or Best-selling. No sales ranking is inferred.')

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.title


class ProductWarranty(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='warranty')
    warranty_type = models.CharField(max_length=20, choices=[('manufacturer', 'Manufacturer'), ('seller', 'Seller'), ('service', 'Service'), ('none', 'No warranty')])
    period_en = models.CharField(max_length=100, blank=True)
    period_bn = models.CharField(max_length=100, blank=True)
    coverage_en = models.TextField(blank=True)
    coverage_bn = models.TextField(blank=True)
    exclusions_en = models.TextField(blank=True)
    exclusions_bn = models.TextField(blank=True)
    claim_steps_en = models.TextField(blank=True)
    claim_steps_bn = models.TextField(blank=True)
    service_phone = models.CharField(max_length=30, blank=True)
    service_email = models.EmailField(blank=True)
    service_address_en = models.TextField(blank=True)
    service_address_bn = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False, help_text='Publish only warranty terms and service contacts verified for this product.')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.product.name} warranty'


class SupportRequest(models.Model):
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    submission_token = models.UUIDField(unique=True, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_requests')
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='support_requests')
    kind = models.CharField(max_length=20, choices=[('contact', 'Contact'), ('order', 'Order support'), ('warranty', 'Warranty')], default='contact')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    message = models.TextField(max_length=5000)
    language = models.CharField(max_length=2, choices=[('en', 'English'), ('bn', 'Bangla')], default='en')
    status = models.CharField(max_length=20, choices=[('new', 'New'), ('in_progress', 'In progress'), ('resolved', 'Resolved'), ('spam', 'Spam')], default='new')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, limit_choices_to={'is_staff': True}, related_name='assigned_support_requests')
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return str(self.reference)


class SupportRateLimit(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)


from .payment_models import PaymentAttempt, PaymentReservation, ManualPaymentClaim, ManualPaymentAudit  # noqa: E402

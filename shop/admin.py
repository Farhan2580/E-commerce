from django.contrib import admin
from .models import (Banner, Brand, Category, HomeSection, Offer, Order, OrderItem,
                     Preorder, Product, ProductImage, ProductVariant, Review,
                     SectionProduct, StoreSettings, Wishlist)
from .models import Coupon, CouponRedemption, OrderStatusEvent, SavedAddress, StockAlert
from .models import BusinessLink, FAQ, InformationPage, InformationSection, ProductWarranty, SupportRequest
from django.urls import reverse
from django import forms
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .models import PaymentAttempt
from . import manual_payment_admin  # Register audited manual payment review.
from .models import Outlet, FooterGroup
from .models import NavigationItem
from .models import DeliveryZone, PCComponent, ProductQuestion


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'shipping_price', 'min_days', 'max_days', 'active', 'position')
    list_editable = ('active', 'position')
    list_filter = ('active',)


@admin.register(ProductQuestion)
class ProductQuestionAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'is_published', 'created_at')
    list_filter = ('is_published',)
    search_fields = ('question', 'product__name')
    readonly_fields = ('user', 'product', 'question', 'created_at')

    def has_add_permission(self, request):
        return False


@admin.register(PCComponent)
class PCComponentAdmin(admin.ModelAdmin):
    list_display = ('product', 'kind', 'socket', 'memory_type', 'active')
    list_filter = ('kind', 'active')
    search_fields = ('product__name',)
    autocomplete_fields = ('product',)


@admin.register(NavigationItem)
class NavigationItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'category', 'brand', 'visible', 'position')
    list_editable = ('visible', 'position')
    list_filter = ('visible',)


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ('name', 'visible', 'position')
    list_editable = ('visible', 'position')
    search_fields = ('name', 'address')


@admin.register(FooterGroup)
class FooterGroupAdmin(admin.ModelAdmin):
    list_display = ('title', 'visible', 'position')
    list_editable = ('visible', 'position')
    filter_horizontal = ('categories', 'brands', 'collections')


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    fields = ('id', 'is_current', 'transaction_id', 'amount', 'currency', 'status', 'bank_transaction', 'expires_at', 'checked_at', 'issue')
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OrderAdminForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if self.instance.pk and self.instance.payment_method in {'CARD', 'ONLINE_BKASH', 'BKASH'}:
            if data.get('status') != self.instance.status and self.instance.payment_status != 'paid':
                raise forms.ValidationError('Online orders require verified payment before changing fulfillment status. Use payment reconciliation for unpaid orders.')
        return data


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ('image', 'alt', 'purpose', 'position')


class WarrantyInline(admin.StackedInline):
    model = ProductWarranty
    extra = 0
    max_num = 1


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        if not data:
            return []
        files = list(data) if isinstance(data, (list, tuple)) else [data]
        if len(files) > 20:
            raise forms.ValidationError('Choose up to 20 images per upload.')
        result = []
        for file in files:
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Each image must be 10 MB or smaller.')
            image = super().clean(file, initial)
            if image.image.format not in {'JPEG', 'PNG', 'WEBP', 'GIF'}:
                raise forms.ValidationError('Use JPEG, PNG, WebP or GIF images.')
            result.append(image)
        return result


class ProductAdminForm(forms.ModelForm):
    gallery_uploads = MultipleImageField(required=False, widget=MultipleImageInput,
        label='Upload gallery images', help_text='Select multiple images at once (up to 20, 10 MB each). JPEG, PNG, WebP or GIF. Existing images are preserved. Edit captions, order and purpose below under Product images.')
    class Meta:
        model = Product
        fields = '__all__'
        help_texts = {'category': 'Choose Phones for mobile phones and Tablets for iPads and other tablets. '
                      'The storefront menu uses these same categories.',
                      'specifications': 'Enter a JSON object with text labels and simple values, '
                      'for example {"Model": "Manufacturer model", "Box contents": "Verified contents"}. '
                      'Use only verified information; leave {} when unknown.'}

    def clean_specifications(self):
        value = self.cleaned_data.get('specifications')
        if value is None:
            return {}
        if not isinstance(value, dict) or any(
                not str(key).strip() or isinstance(item, (dict, list)) or item is None
                for key, item in value.items()):
            raise forms.ValidationError('Use a JSON object with nonempty labels and text, number or boolean values. Nested objects and lists are not supported.')
        return value


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = ('name', 'price', 'stock', 'category', 'brand', 'featured', 'position')
    list_filter = ('category', 'brand', 'featured')
    search_fields = ('name', 'description')
    list_editable = ('featured', 'position')
    inlines = [VariantInline, ImageInline, WarrantyInline]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.has_perm('shop.add_productimage'):
            form.base_fields.pop('gallery_uploads', None)
        return form

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        uploads = form.cleaned_data.get('gallery_uploads', [])
        if uploads and not request.user.has_perm('shop.add_productimage'):
            raise PermissionDenied
        from django.db.models import Max
        last = form.instance.gallery.aggregate(last=Max('position'))['last']
        for offset, image in enumerate(uploads, start=1):
            ProductImage.objects.create(product=form.instance, image=image, alt=form.instance.name,
                                        position=(last if last is not None else -1) + offset)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'featured', 'position')
    list_editable = ('featured', 'position')
    search_fields = ('name',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'featured', 'position')
    list_editable = ('featured', 'position')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'product_name', 'variant_name', 'sku', 'quantity', 'price')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class StatusEventInline(admin.TabularInline):
    model = OrderStatusEvent
    extra = 0
    readonly_fields = ('status', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = ['record_cod_collection']
    form = OrderAdminForm
    list_display = ('id', 'user', 'full_name', 'total_price', 'status', 'payment_method', 'payment_status', 'date_ordered')
    list_filter = ('status', 'payment_method', 'payment_status', 'date_ordered')
    search_fields = ('full_name', 'phone', 'email', 'trx_id')
    readonly_fields = ('user', 'full_name', 'email', 'address', 'phone', 'total_price', 'subtotal', 'shipping_price',
                       'savings', 'coupon_code', 'coupon_discount', 'date_ordered', 'checkout_token', 'payment_method', 'bkash_number', 'trx_id', 'delivery_area', 'delivery_estimate')
    inlines = [OrderItemInline, StatusEventInline, PaymentAttemptInline]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return fields + ('payment_status', 'inventory_released') if obj and obj.payment_method in {'COD', 'CARD', 'ONLINE_BKASH', 'BKASH'} else fields

    def has_record_cod_collection_permission(self, request):
        return self.has_change_permission(request) and request.user.has_perm('shop.record_cod_collection')

    @admin.action(description='Record cash collected for selected COD orders', permissions=['record_cod_collection'])
    def record_cod_collection(self, request, queryset):
        if not self.has_record_cod_collection_permission(request):
            raise PermissionDenied
        count = 0
        with transaction.atomic():
            for order in queryset.select_for_update().filter(payment_method='COD', payment_status='pending').exclude(status='cancelled'):
                order.payment_status = 'paid'
                order.save(update_fields=['payment_status'])
                self.log_change(request, order, 'Cash on Delivery collection recorded by authorized staff.')
                count += 1
        self.message_user(request, f'Recorded collection for {count} COD order(s).')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'status' in form.changed_data:
            OrderStatusEvent.objects.create(order=obj, status=obj.status)

    def has_add_permission(self, request):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'variant_name', 'quantity', 'price')
    readonly_fields = ('order', 'product', 'product_name', 'variant_name', 'sku', 'quantity', 'price')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'is_active', 'exclusive', 'starts_at', 'ends_at')
    list_editable = ('position',)
    list_filter = ('is_active', 'exclusive')
    filter_horizontal = ('products',)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'active', 'position', 'link')
    list_editable = ('active', 'position')


class PlacementInline(admin.TabularInline):
    model = SectionProduct
    extra = 0
    autocomplete_fields = ('product',)


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'active', 'position')
    list_editable = ('active', 'position')
    inlines = [PlacementInline]


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ('updated_at', 'privacy_policy', 'returns_policy', 'shipping_policy')
    fieldsets = (
          ('Store and checkout', {'fields': ('name', 'tagline', 'shipping_price', 'cod_enabled')}),
          ('bKash receiving account — staff only', {'fields': ('bkash_number', 'bkash_account_type', 'bkash_account_confirmed', 'bkash_manual_enabled', 'bkash_manual_approved', 'bkash_manual_instructions', 'bkash_manual_limit'), 'description': 'Entering a number is not account approval. Confirm Merchant/PRA ownership and provider-approved Merchant Payment instructions before enabling. Personal accounts remain unavailable.'}),
          ('Requested settlement destination — staff only', {'fields': ('requested_settlement_account', 'settlement_bank_name', 'settlement_account_holder', 'settlement_branch', 'settlement_routing_number', 'settlement_provider_approved'), 'description': 'The provider must approve and configure settlement in its merchant portal. These fields never route checkout funds.'}),
        ('Verified public contact details', {'fields': ('phone', 'phone_verified', 'email', 'email_verified', 'address', 'address_bn', 'address_verified', 'support_hours_en', 'support_hours_bn')}),
        ('Verified registration details', {'fields': ('license_details_en', 'license_details_bn', 'license_verified')}),
        ('Legacy policies (preserved; edit Information pages)', {'fields': ('privacy_policy', 'returns_policy', 'shipping_policy'), 'classes': ('collapse',)}),
        ('Updates', {'fields': ('updated_at',)}),
    )
    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)


@admin.register(Preorder)
class PreorderAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'name', 'email', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'active', 'kind', 'value', 'minimum_order', 'starts_at', 'ends_at', 'used_count', 'usage_limit')
    list_filter = ('active', 'kind')
    search_fields = ('code',)
    readonly_fields = ('used_count',)
    filter_horizontal = ('products', 'categories', 'customers')


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order', 'created_at')
    readonly_fields = ('coupon', 'user', 'order', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SavedAddress)
class SavedAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'full_name')


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'variant', 'email', 'active', 'sent_at')
    list_filter = ('active', 'sent_at')
    readonly_fields = ('user', 'product', 'variant', 'email', 'created_at', 'sent_at')

    def has_add_permission(self, request):
        return False


class InformationSectionInline(admin.StackedInline):
    model = InformationSection
    extra = 0
    readonly_fields = ('updated_at',)


@admin.register(InformationPage)
class InformationPageAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'slug', 'status', 'footer_group', 'position', 'updated_at')
    list_filter = ('status', 'footer_group')
    search_fields = ('title_en', 'title_bn', 'body_en', 'body_bn')
    readonly_fields = ('updated_at',)
    inlines = [InformationSectionInline]
    fieldsets = (
        (None, {'fields': ('slug', 'status', 'footer_group', 'position', 'updated_at')}),
        ('English', {'fields': ('title_en', 'body_en')}),
        ('বাংলা', {'fields': ('title_bn', 'body_bn')}),
        ('Private publishing checklist', {'fields': ('editorial_notes',)}),
    )

    def view_on_site(self, obj):
        return reverse('policy', args=[obj.slug]) + ('?preview=1' if obj.status == 'draft' else '')

    def get_readonly_fields(self, request, obj=None):
        return ('updated_at', 'slug') if obj else ('updated_at',)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question_en', 'group', 'answer_source', 'status', 'position', 'updated_at')
    list_filter = ('status', 'group', 'answer_source')
    search_fields = ('question_en', 'question_bn', 'answer_en', 'answer_bn')
    readonly_fields = ('updated_at',)


@admin.register(BusinessLink)
class BusinessLinkAdmin(admin.ModelAdmin):
    list_display = ('label_en', 'kind', 'url', 'is_verified', 'position', 'updated_at')
    list_filter = ('is_verified', 'kind')
    readonly_fields = ('updated_at',)


@admin.register(ProductWarranty)
class ProductWarrantyAdmin(admin.ModelAdmin):
    list_display = ('product', 'warranty_type', 'period_en', 'is_verified', 'updated_at')
    list_filter = ('is_verified', 'warranty_type')
    search_fields = ('product__name',)
    readonly_fields = ('updated_at',)
    autocomplete_fields = ('product',)


@admin.register(SupportRequest)
class SupportRequestAdmin(admin.ModelAdmin):
    list_display = ('reference', 'name', 'kind', 'order', 'status', 'assigned_to', 'language', 'created_at', 'updated_at')
    list_filter = ('status', 'kind', 'language', 'created_at')
    search_fields = ('reference', 'name', 'phone', 'email', 'message')
    readonly_fields = ('reference', 'submission_token', 'user', 'order', 'kind', 'name', 'phone', 'email', 'message', 'language', 'created_at', 'updated_at')
    list_select_related = ('order', 'user', 'assigned_to')

    def has_add_permission(self, request):
        return False

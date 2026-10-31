from decimal import Decimal
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction, IntegrityError
from django.db.models import Sum, F, Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_GET
from django.views.decorators.cache import never_cache
from .catalog_csv import SCHEMAS, export_csv, parse_csv, validate_rows
from .admin_helpers import WorkspaceAdmin, OpenClaimFilter
from .models import (Product, ProductVariant, Order, PaymentAttempt, ProductPurpose, Compatibility,
                     PriceAlert, CustomerNotification, ServiceClaim, ClaimEvent, RefundRecord, CatalogActivity)


class PurposeInline(admin.TabularInline):
    model = ProductPurpose
    extra = 0


@admin.register(Compatibility)
class CompatibilityAdmin(WorkspaceAdmin):
    workspace_title = 'Verified accessory compatibility'
    workspace_description = 'Select existing products and record evidence. Verify only when the result applies to every listed option of both products. Verified compatible pairings may appear under Frequently bought together.'
    fieldsets = (('Device and accessory', {'fields': ('device', 'accessory')}), ('Verified result', {'fields': ('compatible', 'evidence', 'verified', 'bought_together')}))
    list_display = ('device', 'accessory', 'compatible', 'verified', 'bought_together')
    list_filter = ('verified', 'compatible', 'bought_together')
    autocomplete_fields = ('device', 'accessory')
    search_fields = ('device__name', 'accessory__name')


@admin.register(ProductPurpose)
class ProductPurposeAdmin(WorkspaceAdmin):
    workspace_title = 'Connect a product to Gadget Finder'
    workspace_description = 'Enter verified suitability and a clear reason. Finder results also check the customer’s budget and the actual available option stock.'
    list_display = ('product', 'purpose', 'verified')
    list_filter = ('purpose', 'verified')
    autocomplete_fields = ('product',)


class ClaimEventInline(admin.TabularInline):
    model = ClaimEvent
    extra = 0
    fields = ('status', 'message', 'created_at')
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceClaim)
class ServiceClaimAdmin(WorkspaceAdmin):
    workspace_title = 'Review a return or warranty request'
    workspace_description = 'Update status and Customer update to publish progress to the order owner. Staff notes stay internal. This form does not issue a refund.'
    fieldsets = (('Customer request', {'fields': ('order', 'item', 'kind', 'reason', 'created_at')}), ('Progress visible to customer', {'fields': ('status', 'customer_update', 'updated_at')}), ('Internal notes', {'fields': ('staff_notes',)}))
    list_display = ('id', 'order', 'item', 'kind', 'status', 'updated_at')
    list_filter = (OpenClaimFilter, 'kind', 'status')
    search_fields = ('order__id', 'item__product_name')
    readonly_fields = ('order', 'item', 'kind', 'reason', 'created_at', 'updated_at')
    inlines = [ClaimEventInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'variant', 'target_price', 'active', 'triggered_at', 'email_sent_at')
    readonly_fields = ('user', 'product', 'variant', 'target_price', 'email', 'created_at', 'triggered_at', 'email_sent_at')
    list_filter = ('active',)

    def has_add_permission(self, request):
        return False


@admin.register(CatalogActivity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'model', 'object_id', 'label', 'source')
    list_filter = ('model', 'source')
    search_fields = ('label', 'actor__username')
    readonly_fields = ('created_at', 'actor', 'model', 'object_id', 'label', 'source', 'changes')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RefundRecord)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('order', 'amount', 'reference', 'recorded_by', 'created_at')
    readonly_fields = ('recorded_by', 'created_at')

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            Order.objects.select_for_update().get(pk=obj.order_id)
            obj.full_clean()
            obj.recorded_by = request.user
            super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.site.admin_view
@require_GET
def store_dashboard(request):
    if not all(request.user.has_perm(f'shop.view_{name}') for name in ('product', 'order')):
        raise PermissionDenied
    paid = Order.objects.filter(payment_status='paid')
    refunds = RefundRecord.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    collected = paid.aggregate(total=Sum('total_price'))['total'] or Decimal('0')
    context = {**admin.site.each_context(request), 'title': 'Store operations',
        'collected': collected, 'refund_total': refunds, 'net_collected': collected - refunds,
        'sales': Order.objects.filter(status='delivered', payment_status='paid').aggregate(total=Sum('subtotal'))['total'] or Decimal('0'),
        'pending': Order.objects.filter(status__in=['received', 'confirmed', 'processing', 'packed']).order_by('date_ordered')[:50],
        'low_products': Product.objects.filter(variants__isnull=True, stock__lte=F('low_stock_threshold')).order_by('stock')[:50],
        'low_variants': ProductVariant.objects.filter(stock__lte=F('product__low_stock_threshold')).select_related('product').order_by('stock')[:50],
        'open_claims': ServiceClaim.objects.exclude(status__in=['resolved', 'rejected']).count()}
    if request.user.has_perm('shop.view_paymentattempt'):
        context['payments'] = PaymentAttempt.objects.filter(is_current=True).values('status').annotate(count=Count('pk'), total=Sum('amount')).order_by('status')
        context['payment_issues'] = PaymentAttempt.objects.filter(is_current=True).filter(
            Q(status='review') | (Q(status='paid') & ~Q(order__payment_status='paid')) |
            (~Q(status='paid') & Q(order__payment_status='paid'))).select_related('order')[:50]
    return render(request, 'admin/shop/store_dashboard.html', context)


class CSVForm(forms.Form):
    kind = forms.ChoiceField(choices=[(name, name.title()) for name in SCHEMAS])
    file = forms.FileField()


@admin.site.admin_view
@never_cache
@require_http_methods(['GET', 'POST'])
def catalog_transfer(request):
    results = None
    form = CSVForm()
    if request.GET.get('export') in SCHEMAS:
        kind = request.GET['export']
        if not request.user.has_perm(f'shop.view_{SCHEMAS[kind][0]._meta.model_name}'):
            raise PermissionDenied
        response = HttpResponse('\ufeff' + export_csv(kind), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{kind}-catalog.csv"'
        return response
    if request.method == 'POST':
        if request.POST.get('action') == 'apply':
            pending = request.session.pop('catalog_csv_preview', None)
            if not pending or pending['user'] != request.user.pk:
                messages.error(request, 'Upload a CSV and review its preview first.')
            else:
                try:
                    with transaction.atomic():
                        validate_rows(pending['kind'], pending['rows'], request.user, apply=True, snapshots=pending['snapshots'])
                    messages.success(request, f'Imported {len(pending["rows"])} validated rows.')
                except (ValidationError, IntegrityError) as exc:
                    messages.error(request, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'A conflicting record was saved. Preview again; nothing was imported.')
            return redirect('catalog_transfer')
        request.session.pop('catalog_csv_preview', None)
        form = CSVForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                kind = form.cleaned_data['kind']
                rows = parse_csv(kind, form.cleaned_data['file'])
                results = validate_rows(kind, rows, request.user)
                if not any(row['errors'] for row in results):
                    request.session['catalog_csv_preview'] = {'kind': kind, 'rows': rows, 'user': request.user.pk,
                        'snapshots': [row['snapshot'] for row in results]}
            except ValidationError as exc:
                form.add_error(None, exc)
    return render(request, 'admin/shop/catalog_transfer.html', {**admin.site.each_context(request),
        'title': 'Catalog CSV import / export', 'form': form, 'results': results,
        'can_apply': bool(request.session.get('catalog_csv_preview'))})

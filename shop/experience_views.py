from decimal import Decimal
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache
from django.utils import timezone

from .commerce import owned_order
from .models import (Category, Compatibility, Product, ProductPurpose, PriceAlert,
                     ServiceClaim, ClaimEvent, CustomerNotification, OrderItem)
from .services import cart_lines, normalized_cart, quantity, set_cart


class FinderForm(forms.Form):
    budget = forms.DecimalField(min_value=Decimal('0.01'), max_digits=8, decimal_places=2)
    purpose = forms.ChoiceField(choices=ProductPurpose.PURPOSES)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)


@require_GET
def gadget_finder(request):
    form = FinderForm(request.GET if 'budget' in request.GET else None, initial={'category': request.GET.get('category', '')})
    matches = []
    if form.is_bound and form.is_valid():
        data = form.cleaned_data
        from .views import products_query
        products = products_query().filter(purposes__purpose=data['purpose'], purposes__verified=True).filter(
            Q(variants__stock__gt=0, variants__price__lte=data['budget']) |
            Q(variants__isnull=True, stock__gt=0, price__lte=data['budget'])).prefetch_related('purposes')
        if data['category']:
            from .views import category_ids
            products = products.filter(category_id__in=category_ids(data['category']))
        for product in products.order_by('catalog_price', 'pk').distinct()[:30]:
            variants = list(product.variants.all())
            options = [item for item in variants or [product] if item.stock is not None and item.stock > 0 and item.price <= data['budget']]
            if options:
                option = min(options, key=lambda item: item.price)
                matches.append({'product': product, 'option': option, 'variant': option if variants else None,
                                'reason': next(p.reason for p in product.purposes.all() if p.verified and p.purpose == data['purpose'])})
        matches.sort(key=lambda match: (match['option'].price, match['product'].pk))
    return render(request, 'shop/gadget_finder.html', {'form': form, 'matches': matches[:30]})


class CompatibilityForm(forms.Form):
    device = forms.ModelChoiceField(queryset=Product.objects.all())
    accessory = forms.ModelChoiceField(queryset=Product.objects.all())


@require_GET
def compatibility_checker(request):
    form = CompatibilityForm(request.GET if 'accessory' in request.GET else None, initial={'device': request.GET.get('device', '')})
    result = None
    checked = form.is_bound and form.is_valid()
    if checked:
        result = Compatibility.objects.filter(device=form.cleaned_data['device'], accessory=form.cleaned_data['accessory'], verified=True).first()
    return render(request, 'shop/compatibility.html', {'form': form, 'result': result, 'checked': checked})


class PriceAlertForm(forms.Form):
    variant = forms.IntegerField(required=False, min_value=1)
    target_price = forms.DecimalField(min_value=Decimal('0.01'), max_digits=8, decimal_places=2)
    email = forms.EmailField(required=False)


@login_required
@require_POST
def subscribe_price(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related('variants'), pk=pk)
    form = PriceAlertForm(request.POST)
    try:
        if not form.is_valid():
            raise ValidationError('Enter a valid target price, option and optional email.')
        data = form.cleaned_data
        variant = get_object_or_404(product.variants, pk=data['variant']) if data['variant'] else None
        if product.has_variants and variant is None:
            raise ValidationError('Choose an exact variant to monitor its price.')
        if data['target_price'] >= (variant or product).price:
            raise ValidationError('Set a target below the current option price.')
        PriceAlert.objects.update_or_create(user=request.user, product=product, variant=variant,
            defaults={'target_price': data['target_price'], 'email': data['email'], 'active': True,
                      'triggered_at': None, 'email_sent_at': None, 'created_at': timezone.now()})
        messages.success(request, 'Price alert saved. You can see notifications in My alerts.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('product_detail', pk=pk)


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def notifications(request):
    if request.method == 'POST':
        if request.POST.get('action') == 'cancel':
            get_object_or_404(PriceAlert, pk=request.POST.get('alert') if request.POST.get('alert', '').isdigit() else 0, user=request.user).delete()
        else:
            CustomerNotification.objects.filter(user=request.user, read=False).update(read=True)
        return redirect('shopping_notifications')
    return render(request, 'shop/notifications.html', {
        'notifications': request.user.shopping_notifications.select_related('product')[:100],
        'price_alerts': request.user.price_alerts.select_related('product', 'variant').order_by('-created_at')[:100]})


def add_lines(request, additions):
    """Validate the complete proposed cart before changing the session."""
    cart = normalized_cart(request.session)
    for product, variant, qty in additions:
        if product.has_variants and variant is None:
            raise ValidationError(f'Choose the current option for {product.name} on its product page.')
        key = f'{product.pk}:{variant.pk}' if variant else str(product.pk)
        cart[key] = quantity(str(cart.get(key, 0) + qty))
    cart_lines({'cart': cart}, strict=True)
    set_cart(request.session, cart)


@require_POST
def buy_again(request, order_id):
    order = owned_order(request, order_id)
    try:
        additions = []
        for line in order.items.select_related('product').all():
            if not line.product:
                raise ValidationError('An item has been removed from the catalog. Please choose a replacement.')
            product = line.product
            variants = product.variants.all()
            variant = None
            if line.variant_name or line.sku:
                candidates = variants.filter(name=line.variant_name)
                if line.sku:
                    candidates = candidates.filter(sku=line.sku)
                variant = candidates.first()
                if not variant:
                    raise ValidationError(f'The purchased option of {product.name} is unavailable. Choose a current option.')
            elif product.has_variants:
                raise ValidationError(f'{product.name} now has variants. Choose a current option.')
            additions.append((product, variant, line.quantity))
        if not additions:
            raise ValidationError('This order has no purchasable items.')
        add_lines(request, additions)
        messages.success(request, 'Items added at current prices. Review your cart before checkout.')
        return redirect('cart_view')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('order_detail', order_id=order.pk)


class ClaimForm(forms.Form):
    item = forms.ModelChoiceField(queryset=OrderItem.objects.none(), label='Purchased item')
    kind = forms.ChoiceField(choices=[('return', 'Return'), ('warranty', 'Warranty')])
    reason = forms.CharField(min_length=10, max_length=3000, widget=forms.Textarea(attrs={'rows': 4}))
    token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = order.items.all()


@never_cache
@require_http_methods(['GET', 'POST'])
def order_services(request, order_id):
    order = owned_order(request, order_id)
    token_key = f'claim_token_{order.pk}'
    token = request.session.setdefault(token_key, str(uuid4()))
    form = ClaimForm(request.POST or None, order=order, initial={'token': token})
    if request.method == 'POST' and form.is_valid():
        if str(form.cleaned_data['token']) != token:
            form.add_error(None, 'This request has already been submitted or expired. Reload to continue.')
        elif order.status != 'delivered':
            form.add_error(None, 'Requests are available after delivery. Contact support for other order issues.')
        else:
            try:
                with transaction.atomic():
                    claim = ServiceClaim.objects.create(order=order, item=form.cleaned_data['item'], kind=form.cleaned_data['kind'], reason=form.cleaned_data['reason'])
                    ClaimEvent.objects.create(claim=claim, status='submitted', message='Request received. Eligibility and next steps will be reviewed by the store.')
                request.session.pop(token_key, None)
                messages.success(request, 'Your request was submitted. Track its progress below.')
                return redirect('order_services', order_id=order.pk)
            except IntegrityError:
                form.add_error(None, 'An open request of this type already exists for that item.')
    return render(request, 'shop/order_services.html', {'order': order, 'form': form,
        'claims': order.service_claims.select_related('item').prefetch_related('events')})


@require_POST
def add_pair(request, pk):
    pair = get_object_or_404(Compatibility.objects.select_related('device', 'accessory'), pk=pk, verified=True, compatible=True, bought_together=True)
    additions = []
    try:
        for prefix, product in [('device', pair.device), ('accessory', pair.accessory)]:
            value = request.POST.get(prefix + '_variant', '')
            if value and not value.isdigit():
                raise ValidationError('Choose a valid option.')
            variant = get_object_or_404(product.variants, pk=value) if value else None
            additions.append((product, variant, 1))
        add_lines(request, additions)
        messages.success(request, 'Both items added at current prices. Check the recorded compatibility details for your chosen options.')
        return redirect('cart_view')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
        return redirect('product_detail', pk=pair.device_id)

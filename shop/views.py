from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError
from django.db.models import Q, Min
from django.db.models.functions import Coalesce
from django.http import JsonResponse, Http404
from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from .forms import AddressForm, CheckoutForm, PreOrderForm, ReviewForm
from .models import (Banner, Brand, Category, HomeSection, Offer, Order, Preorder,
                     Product, ProductVariant, Review, SavedAddress, StockAlert, Wishlist)
from .services import (cart_lines, cart_totals, create_order, normalized_cart,
                       checkout_totals, comparison_ids, enabled_payment_methods, quantity, set_cart, settings_for_store)
from .commerce import accessible_orders, owned_order, remember_guest_order, selected_zone, order_progress


def active_offers():
    now = timezone.now()
    return Offer.objects.filter(is_active=True).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).order_by('position', 'pk')


def products_query():
    return Product.objects.select_related('category', 'brand').prefetch_related('variants').annotate(
        catalog_price=Coalesce(Min('variants__price', filter=Q(variants__stock__gt=0)),
                               Min('variants__price'), 'price')).order_by('position', '-pk')


def category_ids(category):
    # Iterative traversal also tolerates old data if it contains an invalid cycle.
    ids, todo = set(), [category.pk]
    edges = list(Category.objects.values_list('pk', 'parent_id'))
    while todo:
        current = todo.pop()
        if current in ids:
            continue
        ids.add(current)
        todo.extend(pk for pk, parent in edges if parent == current and pk not in ids)
    return ids


def filtered_products(request, category=None, include_scope=False):
    products = products_query()
    q = request.GET.get('q', '').strip()[:200]
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(brand__name__icontains=q))
    category_value = category or request.GET.get('category', '')
    selected = Category.objects.filter(pk=int(category_value)).first() if str(
        category_value).isdigit() else Category.objects.filter(name__iexact=category_value).first()
    if selected:
        products = products.filter(category_id__in=category_ids(selected))
    elif category_value and category_value != 'All':
        products = products.none()
    brand = request.GET.get('brand', '')
    if brand.isdigit():
        products = products.filter(brand_id=brand)
    offer = request.GET.get('offer', '')
    if offer.isdigit():
        products = products.filter(offers__in=active_offers().filter(pk=offer))
    scope = products
    from .catalog import catalog_facets, apply_facets
    facets = catalog_facets(scope, request.GET) if include_scope or any(
        key.startswith(('option_', 'spec_')) for key in request.GET) else []
    products = apply_facets(products, facets, request.GET)
    available = Q(variants__stock__gt=0) | (Q(variants__isnull=True) & (Q(stock__isnull=True) | Q(stock__gt=0)))
    if request.GET.get('availability') == 'available':
        products = products.filter(available)
    elif request.GET.get('availability') == 'out':
        available_ids = Product.objects.filter(available).values('pk')
        products = products.exclude(pk__in=available_ids)
    error = ''
    for field, lookup in [('min_price', 'catalog_price__gte'), ('max_price', 'catalog_price__lte')]:
        value = request.GET.get(field, '')
        if value:
            try:
                amount = Decimal(value)
                if not amount.is_finite() or amount < 0:
                    raise InvalidOperation
                products = products.filter(**{lookup: amount})
            except InvalidOperation:
                error = 'Enter a valid non-negative price.'
                products = products.none()
    sort = request.GET.get('sort', '')
    ordering = {'price_asc': ('catalog_price', 'pk'), 'price_desc': ('-catalog_price', 'pk'),
                'name': ('name', 'pk'), 'newest': ('-pk',)}
    if sort in ordering:
        products = products.order_by(*ordering[sort])
    if include_scope:
        return products, selected, error, scope, facets
    return products, selected, error


def catalog_context(request, category=None):
    products, selected, error, scope, facets = filtered_products(request, category, include_scope=True)
    page = Paginator(products.distinct(), 12).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    allowed_params = {'q', 'category', 'brand', 'min_price', 'max_price', 'availability', 'sort', 'offer'}
    for key in list(params):
        if key not in allowed_params and not key.startswith(('option_', 'spec_')):
            params.pop(key)
    if category:
        params['category'] = str(selected.pk) if selected else str(category)
    from .catalog import collection_presentation
    return {'products': page, 'page_obj': page, 'query_string': params.urlencode(),
            'collection': collection_presentation(request, selected, scope), 'filter_facets': facets,
            'page_numbers': list(page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)),
            'sort_parameters': [(key, value) for key, values in params.lists() for value in values if key != 'sort'],
            'categories': Category.objects.all(), 'brands': Brand.objects.all(),
            'selected_category': str(selected.pk) if selected else '', 'search_query': request.GET.get('q', ''),
            'filter_error': error, 'selected_brand': request.GET.get('brand', '')}


def section_products(section, tab=''):
    placements = list(section.placements.all())
    if placements:
        ids = [p.product_id for p in placements]
        products = list(products_query().filter(pk__in=ids))
        products.sort(key=lambda p: ids.index(p.pk))
    elif section.category_id:
        products = list(products_query().filter(category_id__in=category_ids(section.category))[:24])
    else:
        products = list(products_query().filter(featured=True)[:24])
    tabs = {p.category_id: p.category for p in products}
    if str(tab).isdigit():
        products = [p for p in products if p.category_id == int(tab)]
    return products[:12], list(tabs.values())


@require_GET
def home(request):
    context = catalog_context(request)
    sections = []
    for section in HomeSection.objects.filter(active=True).select_related('category').prefetch_related('placements'):
        tab = request.GET.get('tab', '') if request.GET.get('section') == str(section.pk) else ''
        products, tabs = section_products(section, tab)
        sections.append({'section': section, 'products': products, 'tabs': tabs, 'selected_tab': tab})
    context.update(
        {'banners': Banner.objects.filter(active=True).select_related('product').prefetch_related('product__variants'),
         'featured_categories': Category.objects.filter(featured=True).prefetch_related('products'),
         'hero_products': products_query().filter(image__isnull=False).exclude(image='')[:3],
         'sections': sections,
         'featured_brands': Brand.objects.filter(featured=True, products__isnull=False).distinct(),
         'offers': active_offers().prefetch_related('products')})
    return render(request, 'shop/home.html', context)


@require_GET
def home_section(request, pk):
    section = get_object_or_404(HomeSection.objects.filter(active=True).prefetch_related('placements'), pk=pk)
    products, tabs = section_products(section, request.GET.get('category', ''))
    html = render_to_string('shop/includes/product_grid.html', {'products': products}, request=request)
    return JsonResponse({'html': html})


@require_GET
def product_list(request):
    return render(request, 'shop/product_list.html', catalog_context(request))


@require_GET
def quick_view(request, pk):
    product = get_object_or_404(products_query(), pk=pk)
    return render(request, 'shop/includes/quick_view.html', {'product': product})


def comparison_context(request):
    ids = comparison_ids(request.session)
    products = list(products_query().filter(pk__in=ids))
    products.sort(key=lambda product: ids.index(product.pk))
    specifications = [product.specifications if isinstance(product.specifications, dict) else {} for product in products]
    keys = sorted({key for specs in specifications for key in specs})
    missing = (None, '', [], {})
    rows = [{'label': key, 'values': [specs.get(key) if specs.get(key) not in missing else 'Not provided'
                                    for specs in specifications]} for key in keys]
    return {'products': products, 'rows': rows}


def comparison_response(request, error=''):
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'success': not error, 'error': error, 'ids': comparison_ids(request.session),
                             'html': render_to_string('shop/includes/compare_content.html', comparison_context(request), request=request)},
                            status=400 if error else 200)
    if error:
        messages.error(request, error)
    return redirect('compare')


@never_cache
@require_GET
def compare(request):
    if request.headers.get('Accept') == 'application/json':
        return comparison_response(request)
    return render(request, 'shop/compare.html', comparison_context(request))


@require_POST
def compare_toggle(request, pk):
    get_object_or_404(Product, pk=pk)
    ids = comparison_ids(request.session)
    action = request.POST.get('action', 'toggle')
    error = ''
    if action not in {'add', 'remove', 'toggle'}:
        return comparison_response(request, 'Choose a valid comparison action.')
    if pk in ids and action != 'add':
        ids.remove(pk)
    elif pk not in ids and action != 'remove' and len(ids) < 4:
        ids.append(pk)
    elif pk not in ids and action != 'remove':
        error = 'Compare up to four products. Remove one first.'
    request.session['compare_ids'] = ids
    return comparison_response(request, error)


@require_POST
def compare_clear(request):
    request.session['compare_ids'] = []
    return comparison_response(request)


def cart_state(request):
    lines = cart_lines(request.session)
    totals = checkout_totals(lines, request.user, request.session.get('coupon_code', ''))
    context = {'items': lines, **totals, 'cart_valid': bool(lines) and not any(line['error'] for line in lines)}
    return {'cart_count': sum(line['qty'] for line in lines), 'subtotal': str(totals['subtotal']),
            'total': str(totals['grand_total']),
            'drawer_html': render_to_string('shop/includes/cart_drawer.html', context, request=request),
            'cart_html': render_to_string('shop/includes/cart_content.html', context, request=request)}


@never_cache
@require_GET
def cart_drawer(request):
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'success': True, **cart_state(request)})
    lines = cart_lines(request.session)
    return render(request, 'shop/includes/cart_drawer.html', {'items': lines,
                  'cart_valid': bool(lines) and not any(line['error'] for line in lines),
                  **checkout_totals(lines, request.user, request.session.get('coupon_code', ''))})


@require_POST
def apply_coupon(request):
    code = request.POST.get('coupon_code', '').strip().upper()[:40]
    totals = checkout_totals(cart_lines(request.session), request.user, code)
    if totals['coupon_error']:
        messages.error(request, totals['coupon_error'])
    else:
        request.session['coupon_code'] = code
        request.session.pop('checkout_token', None)
        messages.success(request, 'Coupon applied.' if code else 'Coupon removed.')
    return redirect('cart_view')


def product_detail(request, pk):
    from .models import ProductWarranty
    from .support import language_for, warranty_content
    product = get_object_or_404(products_query().prefetch_related('gallery'), pk=pk)
    existing = Review.objects.filter(product=product,
                                     user=request.user).first() if request.user.is_authenticated else None
    form = ReviewForm(instance=existing)
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = ReviewForm(request.POST, request.FILES, instance=existing)
        if form.is_valid():
            Review.objects.update_or_create(product=product, user=request.user, defaults=form.cleaned_data)
            messages.success(request, 'Your review has been saved.')
            return redirect('product_detail', pk=pk)
    variants = [{'id': v.pk, 'name': v.option_label, 'sku': v.sku, 'price': str(v.price), 'stock': v.stock,
                 'image': v.image.url if v.image else '',
                 'original': str(v.compare_at_price) if v.compare_at_price else ''} for v in product.variants.all()]
    gallery_images, seen_images = [], set()
    sources = [(product.image, product.name)]
    sources += [(image.image, image.alt or product.name) for image in product.gallery.all() if image.purpose == 'gallery']
    sources += [(variant.image, variant.option_label) for variant in product.variants.all()]
    for file, alt in sources:
        if file and file.url not in seen_images:
            seen_images.add(file.url)
            gallery_images.append({'url': file.url, 'alt': alt})
    viewed = [int(value) for value in request.session.get('recently_viewed', []) if str(value).isdigit()][:12]
    recent = list(products_query().filter(pk__in=viewed).exclude(pk=pk))
    recent.sort(key=lambda item: viewed.index(item.pk))
    request.session['recently_viewed'] = [pk] + [value for value in viewed if value != pk][:11]
    warranty = ProductWarranty.objects.filter(product=product, is_verified=True).select_related('product').first()
    from django.db.models import Exists, OuterRef
    from .models import OrderItem
    # A delivered, paid order is the evidence for this label, including COD
    # only after authorized staff have recorded collection.
    qualifying_purchase = OrderItem.objects.filter(
        product=product, order__user_id=OuterRef('user_id'),
        order__status='delivered', order__payment_status='paid')
    reviews = product.reviews.select_related('user').annotate(
        verified_purchase=Exists(qualifying_purchase))
    from .models import DeliveryZone
    from .seo import product_schema, safe_json_ld
    from django import forms as django_forms
    zones = DeliveryZone.objects.filter(active=True)
    zone_field = django_forms.ModelChoiceField(queryset=zones, required=False, empty_label='Choose your area')
    return render(request, 'shop/product_detail.html', {'product': product, 'form': form,
                                                        'delivery_zones': zones, 'delivery_zone_field': zone_field.widget.render('zone', request.GET.get('zone', ''), attrs={'id': 'product-delivery-zone'}),
                                                        'product_schema_json': safe_json_ld(product_schema(request, product, reviews)),
                                                        'product_questions': product.questions.filter(is_published=True).exclude(answer='').select_related('user')[:30],
                                                        'warranty_record': warranty,
                                                        'gallery_images': gallery_images,
                                                        'description_images': [image for image in product.gallery.all() if image.purpose == 'description'],
                                                        'reviews': reviews,
                                                        'recently_viewed': recent[:4],
                                                        'related_products': products_query().filter(category=product.category).exclude(pk=pk)[:4],
                                                        'verified_warranty': warranty_content(warranty, language_for(request)) if warranty else None,
                                                        'variant_data': variants})


def signup(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        accessible_orders(request).filter(user__isnull=True).update(user=user)
        request.session.pop('guest_order_ids', None)
        messages.success(request, 'Your account is ready. Sign in to continue.')
        return redirect('login')
    return render(request, 'shop/signup.html', {'form': form})


def register_view(request):
    return signup(request)


def cart_response(request, success=True, error='', status=200):
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'success': success, 'error': error, **cart_state(request)}, status=status)
    if error:
        messages.error(request, error)
    elif success:
        messages.success(request, 'Cart updated.')
    target = request.POST.get('next', '')
    return redirect(target if target and url_has_allowed_host_and_scheme(target, {request.get_host()}) else 'cart_view')


@require_POST
def add_to_cart(request, pk):
    product = get_object_or_404(products_query(), pk=pk)
    try:
        amount = quantity(request.POST.get('quantity', '1'))
        variant_id = request.POST.get('variant', '')
        variant = next((v for v in product.variants.all() if str(v.pk) == variant_id), None)
        if product.has_variants and not variant:
            raise ValidationError('Choose a valid product variant.')
        if variant_id and not variant:
            raise ValidationError('This variant does not belong to this product.')
        key = f'{pk}:{variant.pk}' if variant else str(pk)
        cart = normalized_cart(request.session)
        new_qty = quantity(str(cart.get(key, 0) + amount))
        item = variant or product
        if item.stock is not None and new_qty > item.stock:
            raise ValidationError(f'Only {item.stock} available. Your cart has not changed.')
        cart[key] = new_qty
        set_cart(request.session, cart)
    except ValidationError as exc:
        return cart_response(request, False, ' '.join(exc.messages), 400)
    return cart_response(request)


@require_POST
def remove_from_cart(request, pk):
    cart = normalized_cart(request.session)
    key = request.POST.get('key', str(pk))
    if key.split(':')[0] != str(pk):
        return cart_response(request, False, 'Invalid cart item.', 400)
    cart.pop(key, None)
    set_cart(request.session, cart)
    return cart_response(request)


@require_GET
def cart_view(request):
    lines = cart_lines(request.session)
    return render(request, 'shop/cart.html', {'items': lines, **checkout_totals(lines, request.user, request.session.get('coupon_code', ''))})


@require_POST
def update_cart(request):
    candidate = normalized_cart(request.session)
    try:
        for key in list(candidate):
            field = 'qty_' + key
            if field in request.POST:
                amount = quantity(request.POST[field], allow_zero=True)
                if amount:
                    candidate[key] = amount
                else:
                    del candidate[key]
        cart_lines({'cart': candidate}, strict=True)
        set_cart(request.session, candidate)
    except ValidationError as exc:
        return cart_response(request, False, ' '.join(exc.messages), 400)
    return cart_response(request)


@require_POST
def clear_cart(request):
    set_cart(request.session, {})
    return cart_response(request)


@never_cache
def checkout(request):
    initial = {'full_name': request.user.get_full_name() if request.user.is_authenticated else '', 'email': request.user.email if request.user.is_authenticated else '',
               'coupon_code': request.session.get('coupon_code', '')}
    initial.update(request.session.get('checkout_shipping', {}))
    initial.setdefault('payment_method', 'COD' if settings_for_store().cod_enabled else '')
    if request.user.is_authenticated and request.method == 'GET' and request.GET.get('address'):
        if not request.GET['address'].isdigit():
            raise Http404
        saved = get_object_or_404(SavedAddress, pk=request.GET['address'], user=request.user)
        initial.update(full_name=saved.full_name, phone=saved.phone, address=saved.address)
    data = request.POST.copy() if request.method == 'POST' else None
    if data is not None:
        request.session['checkout_shipping'] = {key: data.get(key, '')[:limit] for key, limit in
            [('full_name', 100), ('email', 254), ('address', 2000), ('phone', 20), ('payment_method', 20), ('delivery_zone', 20)]}
    if data is not None and 'shipping_address' in data and 'address' not in data:
        data['address'] = data['shipping_address']
    if data is not None and data.get('payment_method') in {'COD', 'CARD', 'ONLINE_BKASH'}:
        data['bkash_number'] = ''
        data['trx_id'] = ''
    if request.method == 'GET':
        request.session.setdefault('checkout_token', str(uuid4()))
    initial['checkout_token'] = request.session.get('checkout_token', '')
    preview = data is not None and data.get('action') == 'preview'
    # Updating an area/coupon is a quote, not an attempt to place the order.
    # Keep entered contact details without showing premature required-field errors.
    form = CheckoutForm(None if preview else data, initial={**initial, **data.dict()} if preview else initial)
    form.fields['payment_method'].choices = enabled_payment_methods()
    from django import forms as django_forms
    form.fields['payment_method'].widget = django_forms.RadioSelect()
    form.fields['payment_method'].widget.choices = form.fields['payment_method'].choices
    if not settings_for_store().bkash_number:
        form.fields.pop('bkash_number')
        form.fields.pop('trx_id')
    status = 200
    if request.method == 'POST' and not preview and form.is_valid():
        try:
            order = create_order(request.user, request.session, form.cleaned_data)
        except (ValidationError, IntegrityError, OperationalError) as exc:
            # A simultaneous submission may have won the token reservation.
            previous = accessible_orders(request).filter(
                                            checkout_token=form.cleaned_data['checkout_token']).first()
            if not previous and str(form.cleaned_data['checkout_token']) == request.session.get('checkout_token'):
                previous = Order.objects.filter(user=request.user if request.user.is_authenticated else None,
                                                checkout_token=form.cleaned_data['checkout_token']).first()
            if previous:
                remember_guest_order(request, previous)
                if request.session.get('checkout_token') == str(previous.checkout_token):
                    request.session['cart'] = {}
                    request.session.pop('coupon_code', None)
                return redirect('order_success_with_id', order_id=previous.pk)
            form.add_error(None, ' '.join(exc.messages) if isinstance(exc,
                                                                      ValidationError) else 'Checkout is busy. Please retry with this same form.')
            status = 400 if isinstance(exc, ValidationError) else 409
        else:
            remember_guest_order(request, order)
            if request.session.get('checkout_token') == str(order.checkout_token):
                request.session['cart'] = {}
                request.session.pop('coupon_code', None)
            if order.payment_method in {'CARD', 'ONLINE_BKASH'}:
                from .payments import initiate
                try:
                    url = initiate(order.payment_attempt.pk)
                except (OperationalError, IntegrityError):
                    url = ''
                if url:
                    return redirect(url)
                messages.warning(request, 'Your order was saved, but hosted payment could not be opened. Check its payment status before paying again.')
            return redirect('order_success_with_id', order_id=order.pk)
    elif request.method == 'POST' and request.POST.get('action') != 'preview':
        status = 400
    lines = cart_lines(request.session)
    if not lines and request.method == 'GET':
        messages.info(request, 'Add a product before checking out.')
        return redirect('product_list')
    coupon_code = data.get('coupon_code', '') if data is not None else initial['coupon_code']
    from .payments import method_ready, accepted_card_brands
    store = settings_for_store()
    bkash_code = 'ONLINE_BKASH' if method_ready('ONLINE_BKASH') else 'BKASH'
    selected = data.get('payment_method', '') if data is not None else initial.get('payment_method', '')
    methods = [
        {'code': 'COD', 'name': 'Cash on Delivery', 'icon': 'cash', 'ready': settings_for_store().cod_enabled,
         'instructions': 'Pay the courier when your order arrives. Your order stays unpaid until the store records collection.'},
        {'code': bkash_code, 'name': 'bKash', 'icon': 'wallet', 'ready': method_ready('ONLINE_BKASH') or store.manual_bkash_ready,
         'instructions': 'Continue to the provider’s secure checkout.' if bkash_code == 'ONLINE_BKASH' else 'Place your order to see the verified receiving details, exact amount and payment reference. Your payment will need store verification.'},
        {'code': 'CARD', 'name': 'Card', 'icon': 'card', 'ready': method_ready('CARD'),
         'instructions': 'Pay securely on the provider’s page. Enter your card details only there.'},
    ]
    delivery_error = ''
    try:
        zone = selected_zone(data.get('delivery_zone') if data is not None else initial.get('delivery_zone'))
    except ValidationError as error:
        zone = None
        delivery_error = ' '.join(error.messages)
    return render(request, 'shop/checkout.html', {'form': form, 'cart_items': lines, 'addresses': request.user.addresses.all() if request.user.is_authenticated else [],
                                                'delivery_quote': zone,
                                                'delivery_error': delivery_error,
                                                'payment_choices': methods, 'selected_payment': selected,
                                                'accepted_card_brands': accepted_card_brands() if method_ready('CARD') else [],
                                                'payments_available': any(method['ready'] for method in methods),
                                                'card_ready': 'CARD' in dict(enabled_payment_methods()),
                                                'bkash_ready': 'ONLINE_BKASH' in dict(enabled_payment_methods()),
                                                **checkout_totals(lines, request.user, coupon_code, delivery_zone=zone)},
                  status=status)


@never_cache
@require_GET
def order_success(request, order_id):
    if not request.user.is_authenticated and not request.session.get('guest_order_ids'):
        return redirect(reverse('login') + '?next=' + request.path)
    order = owned_order(request, order_id)
    return render(request, 'shop/order_success.html', {'order': order, 'order_progress': order_progress(order), **manual_payment_context(order)})


def manual_payment_context(order):
    from .forms import ManualReferenceForm
    from django.utils import timezone
    store = settings_for_store()
    attempt = order.payment_attempt
    return {'manual_reference_form': ManualReferenceForm(),
            'manual_payment_available': bool(attempt and attempt.provider == 'manual_bkash'
                and store.manual_bkash_ready and store.bkash_number == attempt.manual_receiver
                and not order.inventory_released and attempt.expires_at > timezone.now())}


@never_cache
@require_GET
def order_detail(request, order_id):
    if not request.user.is_authenticated and not request.session.get('guest_order_ids'):
        return redirect(reverse('login') + '?next=' + request.path)
    order = owned_order(request, order_id)
    return render(request, 'shop/order_detail.html', {'order': order, 'order_progress': order_progress(order), 'items': order.items.all(), **manual_payment_context(order)})


@login_required
@require_GET
def order_history(request):
    return render(request, 'shop/order_history.html', {
        'orders': Order.objects.filter(user=request.user).prefetch_related('items').order_by('-date_ordered'),
        'preorders': Preorder.objects.filter(user=request.user)})


def my_orders(request):
    return order_history(request)


@require_GET
def offers(request):
    return render(request, 'shop/offers.html',
                  {'offers': active_offers().prefetch_related('products')})


@login_required
def preorder(request):
    form = PreOrderForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.user = request.user
        entry.save()
        messages.success(request, 'Your preorder request has been received.')
        return redirect('order_history')
    return render(request, 'shop/preorder.html', {'form': form})


@require_GET
def preorder_thanks(request):
    return render(request, 'shop/preorder_thanks.html')


@require_GET
def ajax_products(request):
    products, selected, error = filtered_products(request)
    return JsonResponse({'products': [{'id': p.pk, 'name': p.name, 'price': str(p.selling_price),
                                       'url': reverse('product_detail', args=[p.pk]),
                                       'image': p.image.url if p.image else '',
                                       'availability': p.availability} for p in products[:8]], 'error': error})


@login_required
@require_POST
def ajax_submit_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    existing = Review.objects.filter(product=product, user=request.user).first()
    form = ReviewForm(request.POST, request.FILES, instance=existing)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    review, created = Review.objects.update_or_create(product=product, user=request.user, defaults=form.cleaned_data)
    return JsonResponse(
        {'success': True, 'review': {'user': request.user.username, 'rating': review.rating, 'comment': review.comment,
                                     'created_at': review.created_at.isoformat()},
         'summary': f'{product.reviews.count()} review(s)'})


def legacy_category(request, names):
    category = Category.objects.filter(name__in=names).first()
    return render(request, 'shop/product_list.html',
                  catalog_context(request, category.pk if category else '__missing__'))


def laptop_desktop(request):
    return legacy_category(request, ['Laptop', 'Laptop & Desktop'])


def phones_tablets(request):
    return legacy_category(request, ['Phones & Tablets'])


def sound_equipment(request):
    return legacy_category(request, ['Sound Equipment'])


def power_accessories(request):
    return legacy_category(request, ['Power'])


def fitness_wearable(request):
    return legacy_category(request, ['Watch', 'Fitness', 'Fitness & Wearable'])


def smart_electronics(request):
    return legacy_category(request, ['Smart Tech'])


@login_required
def profile_view(request):
    instance = None
    address_id = request.POST.get('address_id') if request.method == 'POST' else request.GET.get('edit')
    if address_id:
        if not address_id.isdigit():
            raise Http404
        instance = get_object_or_404(SavedAddress, pk=address_id, user=request.user)
    form = AddressForm(request.POST if request.method == 'POST' else None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, 'Address saved.')
        return redirect('profile')
    return render(request, 'shop/profile.html', {'address_form': form, 'editing_address': instance,
                                               'addresses': request.user.addresses.all(),
                                               'saved_products': products_query().filter(wishlist__user=request.user)[:4],
                                               'recent_orders': request.user.orders.order_by('-date_ordered')[:5]})


@login_required
@require_POST
def subscribe_stock(request, pk):
    product = get_object_or_404(products_query(), pk=pk)
    variant = None
    try:
        email = forms.EmailField().clean(request.POST.get('email', ''))
        variant_id = request.POST.get('variant', '')
        if variant_id:
            if not variant_id.isdigit():
                raise ValidationError('Select a valid option.')
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
        if product.has_variants and not variant:
            raise ValidationError('Select the option you want to track.')
        item = variant or product
        if item.stock is None or item.stock > 0:
            raise ValidationError('This item is already available to order.')
        StockAlert.objects.update_or_create(user=request.user, product=product, variant=variant,
                                           defaults={'email': email, 'active': True, 'sent_at': None})
        messages.success(request, 'Stock alert saved. Email delivery requires the store’s email service to be configured.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    return redirect('product_detail', pk=pk)


@login_required
@require_POST
def unsubscribe_stock(request, pk):
    alert = get_object_or_404(StockAlert, pk=pk, user=request.user)
    alert.active = False
    alert.save(update_fields=['active'])
    messages.success(request, 'Stock alert cancelled.')
    return redirect('profile')


@login_required
@require_POST
def delete_address(request, pk):
    get_object_or_404(SavedAddress, pk=pk, user=request.user).delete()
    messages.success(request, 'Address removed.')
    return redirect('profile')


@never_cache
@require_GET
def wishlist(request):
    products = products_query().filter(wishlist__user=request.user) if request.user.is_authenticated else Product.objects.none()
    if request.headers.get('Accept') == 'application/json':
        ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True)) if request.user.is_authenticated else []
        result = {'success': True, 'wishlist_ids': ids}
        if request.GET.get('cards') == '1':
            result['html'] = render_to_string('shop/includes/product_grid.html', {'products': products}, request=request) if ids else ''
        return JsonResponse(result)
    return render(request, 'shop/wishlist.html', {'products': products})


@require_POST
def toggle_wishlist(request, pk):
    if not request.user.is_authenticated:
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'success': False, 'login_url': reverse('login') + '?next=' + reverse('wishlist')}, status=401)
        return redirect(reverse('login') + '?next=' + reverse('wishlist'))
    product = get_object_or_404(Product, pk=pk)
    action = request.POST.get('action', 'toggle')
    if action not in {'save', 'remove', 'toggle'}:
        return JsonResponse({'success': False, 'error': 'Choose a valid wishlist action.'}, status=400)
    if action == 'remove':
        Wishlist.objects.filter(user=request.user, product=product).delete()
        saved = False
    else:
        entry, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        saved = True
        if action == 'toggle' and not created:
            entry.delete()
            saved = False
    if request.headers.get('Accept') == 'application/json':
        ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
        return JsonResponse({'success': True, 'saved': saved, 'product_id': product.pk,
                             'wishlist_ids': ids, 'wishlist_count': len(ids)})
    messages.success(request, 'Saved to wishlist.' if saved else 'Removed from wishlist.')
    return redirect('wishlist')


def policy(request, slug):
    from .support_views import information
    return information(request, slug)

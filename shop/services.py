"""Single source of truth for session carts, inventory and order totals."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Coupon, CouponRedemption, Order, OrderItem, OrderStatusEvent, Product, ProductVariant, StoreSettings


def settings_for_store():
    return StoreSettings.objects.filter(pk=1).first() or StoreSettings()


def enabled_payment_methods(store=None):
    store = store or settings_for_store()
    result = [('COD', 'Cash on Delivery')] if store.cod_enabled else []
    if store.manual_bkash_ready:
        result.append(('BKASH', 'bKash — manual transfer verification'))
    from .payments import method_ready
    result.extend((code, label) for code, label in [('CARD', 'Card — secure hosted checkout'),
                  ('ONLINE_BKASH', 'bKash — secure hosted checkout')] if method_ready(code))
    return result


def quantity(value, allow_zero=False):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValidationError('Enter a whole-number quantity.')
    if str(result) != str(value) or not (0 if allow_zero else 1) <= result <= 99:
        raise ValidationError('Quantity must be a whole number between 1 and 99 (or 0 to remove).')
    return result


def normalized_cart(session):
    result = {}
    stored = session.get('cart', {})
    if not isinstance(stored, dict):
        return result
    for key, value in stored.items():
        try:
            parts = str(key).split(':')
            if len(parts) > 2 or any(not part.isdigit() for part in parts):
                continue
            qty = quantity(value.get('quantity') if isinstance(value, dict) else value)
            result[str(key)] = qty
        except ValidationError:
            continue
    return result


def comparison_ids(session):
    stored = session.get('compare_ids', [])
    candidates = list(dict.fromkeys(value for value in stored if type(value) is int and value > 0)) if isinstance(stored, list) else []
    existing = set(Product.objects.filter(pk__in=candidates[:100]).values_list('pk', flat=True))
    ids = [pk for pk in candidates[:100] if pk in existing][:4]
    if stored != ids:
        session['compare_ids'] = ids
    return ids


def cart_lines(session, strict=False):
    cart = normalized_cart(session)
    products = {p.pk: p for p in Product.objects.filter(pk__in=[k.split(':')[0] for k in cart]).select_related(
        'category').prefetch_related('variants')}
    lines = []
    for key, qty in cart.items():
        ids = key.split(':')
        product = products.get(int(ids[0]))
        variant = next((v for v in product.variants.all() if len(ids) == 2 and v.pk == int(ids[1])),
                       None) if product else None
        error = ''
        if not product:
            error = 'This product is no longer available. Remove it to continue.'
        elif product.has_variants and variant is None:
            error = f'Choose a current variant for {product.name}. Remove this old cart item first.'
        elif len(ids) == 2 and variant is None:
            error = 'This variant no longer exists. Remove it to continue.'
        item = variant or product
        if item and item.stock is not None and qty > item.stock:
            error = f'{product.name}: only {item.stock} available.'
        if strict and error:
            raise ValidationError(error)
        price = item.price if item else Decimal('0')
        original = item.compare_at_price if item else None
        image = (variant.image if variant and variant.image else product.image) if product else None
        lines.append(
            {'key': key, 'product_id': int(ids[0]), 'product': product, 'variant': variant, 'qty': qty, 'quantity': qty,
             'price': price, 'subtotal': price * qty, 'total_price': price * qty,
             'savings': max((original or price) - price, Decimal('0')) * qty, 'error': error,
             'image_url': image.url if image else '',
             'stock_limit': min(99, item.stock) if item and item.stock is not None else 99})
    return lines


def cart_totals(lines, settings=None):
    settings = settings or settings_for_store()
    subtotal = sum((line['subtotal'] for line in lines), Decimal('0'))
    savings = sum((line['savings'] for line in lines), Decimal('0'))
    shipping = settings.shipping_price if lines else Decimal('0')
    return {'subtotal': subtotal, 'savings': savings, 'shipping': shipping, 'grand_total': subtotal + shipping}


def set_cart(session, cart):
    session['cart'] = cart
    session.pop('checkout_token', None)
    session.modified = True


def coupon_amount(coupon, lines, user):
    now = timezone.now()
    if not coupon.active or (coupon.starts_at and now < coupon.starts_at) or (coupon.ends_at and now >= coupon.ends_at):
        raise ValidationError('This coupon is not currently active.')
    if not user.is_authenticated:
        raise ValidationError('Sign in to use a coupon.')
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValidationError('This coupon has reached its usage limit.')
    if coupon.redemptions.filter(user=user).count() >= coupon.per_customer_limit:
        raise ValidationError('You have already used this coupon the allowed number of times.')
    customers = set(coupon.customers.values_list('pk', flat=True))
    if customers and user.pk not in customers:
        raise ValidationError('This coupon is not available for your account.')
    product_ids = set(coupon.products.values_list('pk', flat=True))
    category_ids = set(coupon.categories.values_list('pk', flat=True))
    eligible = sum((line['subtotal'] for line in lines if line['product'] and (
        not product_ids and not category_ids or line['product_id'] in product_ids or line['product'].category_id in category_ids)), Decimal('0'))
    if eligible <= 0 or eligible < coupon.minimum_order:
        raise ValidationError('Eligible items do not meet this coupon’s minimum order value.')
    if coupon.value <= 0 or (coupon.kind == 'percent' and coupon.value > 100):
        raise ValidationError('This coupon has invalid discount settings.')
    discount = eligible * coupon.value / 100 if coupon.kind == 'percent' else coupon.value
    return min(eligible, discount.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def checkout_totals(lines, user, code='', strict=False, reserve=False, delivery_zone=None):
    totals = cart_totals(lines)
    from .models import DeliveryZone
    totals['shipping_pending'] = bool(lines and not delivery_zone and DeliveryZone.objects.filter(active=True).exists())
    if totals['shipping_pending']:
        totals['grand_total'] -= totals['shipping']
        totals['shipping'] = Decimal('0')
    if delivery_zone and lines:
        totals['grand_total'] += delivery_zone.shipping_price - totals['shipping']
        totals['shipping'] = delivery_zone.shipping_price
    totals.update(coupon_code=code.strip().upper(), coupon_discount=Decimal('0'), coupon_error='')
    if totals['coupon_code']:
        try:
            queryset = Coupon.objects.select_for_update() if reserve else Coupon.objects
            coupon = queryset.filter(code__iexact=totals['coupon_code']).first()
            if not coupon:
                raise ValidationError('Coupon not found.')
            totals['coupon_discount'] = coupon_amount(coupon, lines, user)
            if reserve:
                allowed = Coupon.objects.filter(pk=coupon.pk)
                if coupon.usage_limit is not None:
                    allowed = allowed.filter(used_count__lt=coupon.usage_limit)
                if not allowed.update(used_count=F('used_count') + 1):
                    raise ValidationError('This coupon has reached its usage limit.')
                totals['coupon'] = coupon
        except ValidationError as exc:
            if strict:
                raise
            totals['coupon_error'] = ' '.join(exc.messages)
    totals['grand_total'] -= totals['coupon_discount']
    return totals


@transaction.atomic
def create_order(user, session, data):
    # Serialize this customer's checkouts before testing the idempotency key.
    # Also protects per-customer coupon limits across different checkout tokens.
    # SQLite uses its database write lock; PostgreSQL locks this account row.
    from django.contrib.auth import get_user_model
    customer = user if user.is_authenticated else None
    if customer:
        get_user_model().objects.select_for_update().get(pk=customer.pk)
    token = UUID(str(data['checkout_token']))
    previous = Order.objects.filter(checkout_token=token, user=customer).first()
    if previous and (customer or previous.pk in session.get('guest_order_ids', []) or str(token) == session.get('checkout_token')):
        return previous
    if str(token) != session.get('checkout_token'):
        raise ValidationError('Checkout expired or changed. Reload checkout and try again.')
    lines = cart_lines(session, strict=True)
    if not lines:
        raise ValidationError('Your cart is empty.')
    store = settings_for_store()
    if data['payment_method'] not in dict(enabled_payment_methods(store)):
        raise ValidationError('This payment method is not currently enabled.')
    if data['payment_method'] == 'BKASH' and not store.manual_bkash_ready:
        raise ValidationError('bKash is currently unavailable. Choose another payment method.')
    # A unique token arbitrates simultaneous repeats. All reservations and writes
    # roll back together if a later line runs out of stock.
    from .commerce import selected_zone
    zone = selected_zone(data.get('delivery_zone'), required=True, lock=True)
    totals = checkout_totals(lines, user, data.get('coupon_code', session.get('coupon_code', '')), strict=True, reserve=True, delivery_zone=zone)
    order = Order.objects.create(user=customer, checkout_token=token,
                                 delivery_area=zone.name if zone else '', delivery_estimate=zone.estimate if zone else '',
                                 full_name=data['full_name'], email=data['email'], address=data['address'],
                                 phone=data['phone'],
                                 payment_method=data['payment_method'],
                                 bkash_number='', trx_id='', payment_status='pending',
                                 total_price=totals['grand_total'], subtotal=totals['subtotal'],
                                 shipping_price=totals['shipping'], savings=totals['savings'],
                                 coupon_code=totals['coupon_code'], coupon_discount=totals['coupon_discount'])
    if totals.get('coupon'):
        CouponRedemption.objects.create(coupon=totals['coupon'], user=user, order=order)
    OrderStatusEvent.objects.create(order=order, status='received')
    online = data['payment_method'] in {'CARD', 'ONLINE_BKASH', 'BKASH'}
    if online:
        from .models import PaymentAttempt
        from datetime import timedelta
        order.status = 'awaiting_payment'
        order.save(update_fields=['status'])
        order.status_events.update(status='awaiting_payment')
        manual = data['payment_method'] == 'BKASH'
        if manual and not Decimal('0') < order.total_price <= store.bkash_manual_limit:
            raise ValidationError('This amount is outside the available bKash payment limit. Choose another method.')
        if not manual and not Decimal('10') <= order.total_price <= Decimal('500000'):
            raise ValidationError('Online payment supports totals from BDT 10 to BDT 500,000.')
        if not manual and len(order.email) > 50:
            raise ValidationError('The gateway requires an email address of at most 50 characters.')
        PaymentAttempt.objects.create(order=order, amount=order.total_price,
            provider='manual_bkash' if manual else 'sslcommerz',
            manual_receiver=store.bkash_number if manual else '',
            manual_instructions=store.bkash_manual_instructions if manual else '',
            expires_at=timezone.now() + (timedelta(hours=24) if manual else timedelta(minutes=30)))
    for line in sorted(lines, key=lambda line: line['key']):
        item = line['variant'] or line['product']
        model = ProductVariant if line['variant'] else Product
        # Locks on supported databases; the conditional UPDATE also prevents
        # overselling on SQLite, which does not implement row-level FOR UPDATE.
        current = model.objects.select_for_update().get(pk=item.pk)
        if current.price != line['price']:
            raise ValidationError('A price changed during checkout. Reload and review your total.')
        if current.stock is not None:
            reserved = model.objects.filter(pk=current.pk, stock__gte=line['qty']).update(
                stock=F('stock') - line['qty'])
            if not reserved:
                raise ValidationError(f'{line["product"].name} has insufficient stock. Please update your cart.')
            if online:
                from .models import PaymentReservation
                PaymentReservation.objects.create(order=order, quantity=line['qty'],
                    product=line['product'] if not line['variant'] else None, variant=line['variant'])
        OrderItem.objects.create(order=order, product=line['product'], product_name=line['product'].name,
                                 variant_name=line['variant'].name if line['variant'] else '',
                                 sku=line['variant'].sku if line['variant'] else '',
                                 quantity=line['qty'], price=line['price'])
    return order

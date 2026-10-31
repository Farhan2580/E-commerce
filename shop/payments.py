"""SSLCOMMERZ v4 hosted sandbox checkout; fail closed on ambiguous results.

Never log request/response bodies or exception strings: validation URLs contain
credentials and provider responses may contain payment instrument metadata.
"""
import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from .models import (Order, PaymentAttempt, Product, ProductVariant,
                     Coupon, CouponRedemption, OrderStatusEvent)

BASE = 'https://sandbox.sslcommerz.com'
ONLINE_METHODS = {'CARD', 'ONLINE_BKASH'}
CARD_BRANDS = {
    'visa': {'name': 'Visa', 'gateway': 'visacard', 'asset': 'shop/payment-brands/visa.svg'},
    'mastercard': {'name': 'Mastercard', 'gateway': 'mastercard', 'asset': 'shop/payment-brands/mastercard.png'},
}


def accepted_card_brands():
    configured = settings.SSLCOMMERZ_CARD_BRANDS
    if not configured or any(brand not in CARD_BRANDS for brand in configured):
        return []
    return [CARD_BRANDS[brand] for brand in dict.fromkeys(configured)]


class GatewayUnavailable(Exception):
    pass


class GatewayReview(GatewayUnavailable):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def method_ready(method):
    if method not in ONLINE_METHODS:
        return False
    public = urlsplit(settings.PAYMENT_PUBLIC_URL)
    return bool(settings.SSLCOMMERZ_STORE_ID and settings.SSLCOMMERZ_STORE_PASSWORD
                and public.scheme == 'https' and public.hostname
                and not public.username and not public.password
                and not public.path and not public.query and not public.fragment
                and len(settings.PAYMENT_PUBLIC_URL) <= 180
                and (settings.SSLCOMMERZ_CARD_ENABLED and accepted_card_brands() if method == 'CARD'
                     else settings.SSLCOMMERZ_BKASH_ENABLED))


@sensitive_variables()
def api(path, params, post=False):
    params = dict(params, store_id=settings.SSLCOMMERZ_STORE_ID,
                  store_passwd=settings.SSLCOMMERZ_STORE_PASSWORD, format='json')
    encoded = urlencode(params).encode()
    request = Request(BASE + path + ('' if post else '?' + encoded.decode()),
                      data=encoded if post else None)
    try:
        with build_opener(NoRedirect).open(request, timeout=15) as response:
            result = json.loads(response.read(512_001))
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (URLError, TimeoutError, OSError, ValueError):
        raise GatewayUnavailable('Provider unavailable; payment remains unconfirmed.') from None


def safe_checkout_url(url):
    parts = urlsplit(url)
    return (parts.scheme == 'https' and parts.hostname == 'sandbox.sslcommerz.com'
            and parts.port in (None, 443) and not parts.username and not parts.password)


@sensitive_variables()
def initiate(attempt_id):
    """Claim once before network I/O. Never retry an ambiguous session creation."""
    attempt = PaymentAttempt.objects.select_related('order').get(pk=attempt_id)
    if (attempt.provider != 'sslcommerz' or not attempt.is_current or attempt.order.payment_status == 'review'
            or attempt.order.inventory_released or attempt.order.status != 'awaiting_payment'):
        return ''
    if not method_ready(attempt.order.payment_method):
        return ''
    if attempt.expires_at <= timezone.now():
        reconcile(attempt.pk)
        return ''
    if not PaymentAttempt.objects.filter(pk=attempt.pk, status='created').update(status='initiating'):
        attempt.refresh_from_db()
        return attempt.checkout_url if attempt.status == 'pending' and safe_checkout_url(attempt.checkout_url) else ''
    order = attempt.order
    callback = settings.PAYMENT_PUBLIC_URL + '/payments/return/' + str(attempt.pk) + '/'
    params = dict(total_amount=str(attempt.amount), currency=attempt.currency, tran_id=attempt.transaction_id,
                  success_url=callback, fail_url=callback, cancel_url=callback,
                  ipn_url=settings.PAYMENT_PUBLIC_URL + '/payments/ipn/' + str(attempt.pk) + '/',
                  cus_name=order.full_name[:50], cus_email=order.email, cus_add1=order.address[:50],
                  cus_city='Not supplied', cus_country='Bangladesh', cus_phone=order.phone,
                  shipping_method='YES', ship_name=order.full_name[:50], ship_add1=order.address[:50],
                  ship_city='Not supplied', ship_country='Bangladesh', ship_postcode='0000',
                  num_of_item=sum(order.items.values_list('quantity', flat=True)),
                  product_name='GadgetFlow order ' + str(order.pk), product_category='Electronics',
                  product_profile='physical-goods', value_a=str(order.pk), emi_option=0,
                  multi_card_name='bkash' if order.payment_method == 'ONLINE_BKASH'
                  else ','.join(brand['gateway'] for brand in accepted_card_brands()))
    try:
        result = api('/gwprocess/v4/api.php', params, post=True)
        url = result.get('GatewayPageURL', '')
        if result.get('status') != 'SUCCESS' or not result.get('sessionkey') or not safe_checkout_url(url):
            raise GatewayUnavailable
    except (GatewayUnavailable, ValueError, TypeError):
        PaymentAttempt.objects.filter(pk=attempt.pk, status='initiating').update(
            status='pending', issue='session_creation_uncertain')
        return ''
    # Callback may already have settled the attempt; do not overwrite it.
    updated = PaymentAttempt.objects.filter(pk=attempt.pk, status='initiating').update(
        status='pending', session_key=result['sessionkey'], checkout_url=url)
    return url if updated else ''


@sensitive_variables()
def query(attempt):
    if not settings.SSLCOMMERZ_STORE_ID or not settings.SSLCOMMERZ_STORE_PASSWORD:
        raise GatewayUnavailable
    result = api('/validator/api/merchantTransIDvalidationAPI.php', {'tran_id': attempt.transaction_id})
    if result.get('APIConnect') != 'DONE' or not isinstance(result.get('element'), list):
        raise GatewayUnavailable
    records = result['element']
    if not all(isinstance(record, dict) for record in records):
        raise GatewayUnavailable
    if not records:
        return None
    successes = [r for r in records if r.get('status') in {'VALID', 'VALIDATED'}]
    if len(successes) > 1:
        raise GatewayReview  # Multiple charges require manual reconciliation.
    if successes:
        record = successes[0]
        val_id = record.get('val_id')
        if not val_id:
            raise GatewayUnavailable
        verified = api('/validator/api/validationserverAPI.php', {'val_id': val_id, 'v': 1})
        if (verified.get('APIConnect') != 'DONE' or verified.get('val_id') != val_id
                or verified.get('status') not in {'VALID', 'VALIDATED'}):
            raise GatewayUnavailable
        return verified
    # Only accept a terminal failure when ALL provider records are terminal.
    if all(r.get('status') in {'FAILED', 'CANCELLED', 'CANCEL'} for r in records):
        return records[-1]
    return None


def matches(record, attempt, order):
    try:
        amount = Decimal(str(record.get('amount', '')))
        return (amount.is_finite() and amount == attempt.amount == order.total_price
                and record.get('currency') == attempt.currency == 'BDT'
                and record.get('tran_id') == attempt.transaction_id
                and str(record.get('value_a')) == str(order.pk))
    except (InvalidOperation, ValueError, TypeError):
        return False


def release(order):
    """Called with the order locked, once. Never touch historical/COD inventory."""
    if order.inventory_released:
        return
    for reservation in order.payment_reservations.order_by('pk'):
        model = ProductVariant if reservation.variant_id else Product
        pk = reservation.variant_id or reservation.product_id
        item = model.objects.select_for_update().filter(pk=pk, stock__isnull=False).first()
        if item:
            model.objects.filter(pk=pk, stock__isnull=False).update(stock=F('stock') + reservation.quantity)
            from .activity import record_activity
            record_activity(item, {'stock': {'before': str(item.stock), 'after': str(item.stock + reservation.quantity)}}, source=f'payment release order {order.pk}')
    for redemption in CouponRedemption.objects.filter(order=order):
        Coupon.objects.filter(pk=redemption.coupon_id, used_count__gt=0).update(used_count=F('used_count') - 1)
    CouponRedemption.objects.filter(order=order).delete()
    order.inventory_released = True


@sensitive_variables()
def reconcile(attempt_id):
    attempt = PaymentAttempt.objects.get(pk=attempt_id)
    if attempt.status == 'paid':
        return 'paid'
    if attempt.provider == 'manual_bkash':
        from django.db import transaction
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=attempt.order_id)
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
            if attempt.status == 'paid':
                return 'paid'
            if attempt.expires_at <= timezone.now() and not order.inventory_released:
                release(order)
                order.status = 'cancelled'
                order.payment_status = 'review' if hasattr(attempt, 'manual_claim') else 'expired'
                attempt.status = 'review' if hasattr(attempt, 'manual_claim') else 'expired'
                attempt.issue = 'manual_reservation_expired'
                attempt.save(update_fields=['status', 'issue'])
                order.save(update_fields=['status', 'payment_status', 'inventory_released'])
                OrderStatusEvent.objects.create(order=order, status='cancelled')
            return order.payment_status
    try:
        record = query(attempt)
        issue = '' if record else 'provider_unconfirmed'
    except GatewayReview:
        record, issue = None, 'multiple_provider_payments'
    except GatewayUnavailable:
        record, issue = None, 'verification_unavailable'
    try:
        return apply_result(attempt_id, record, issue)
    except IntegrityError:
        # Another order may have claimed this bank transaction concurrently.
        # The first atomic application rolled back; re-read the committed claim.
        return apply_result(attempt_id, record, issue)


@transaction.atomic
@sensitive_variables()
def apply_result(attempt_id, record, issue=''):
    order_id = PaymentAttempt.objects.only('order_id').get(pk=attempt_id).order_id
    order = Order.objects.select_for_update().get(pk=order_id)
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
    if attempt.status == 'paid':
        return 'paid'
    if not attempt.is_current:
        # A stale failure must never cancel/release a newer attempt. A late
        # success on the old transaction requires review of possible double payment.
        if (record and record.get('status') in {'VALID', 'VALIDATED'}) or issue == 'multiple_provider_payments':
            attempt.status = 'review'
            attempt.issue = 'late_superseded_payment'
            order.payment_status = 'review'
            order.save(update_fields=['payment_status'])
            attempt.save(update_fields=['status', 'issue'])
        return order.payment_status
    expired = attempt.expires_at <= timezone.now()
    status = attempt.status
    if issue == 'multiple_provider_payments':
        status = 'review'
    if order.payment_attempts.filter(is_current=False, status='review').exists():
        status, issue = 'review', 'superseded_payment_needs_review'
    if record:
        if not matches(record, attempt, order):
            status, issue = 'review', 'identity_amount_currency_mismatch'
        elif record.get('status') in {'VALID', 'VALIDATED'}:
            bank_id = record.get('bank_tran_id')
            if (not bank_id or str(record.get('risk_level')) != '0'
                    or PaymentAttempt.objects.filter(bank_transaction=bank_id).exclude(pk=attempt.pk).exists()):
                status, issue = 'review', 'transaction_or_risk_review'
            elif (order.inventory_released or order.status != 'awaiting_payment'
                  or order.payment_attempts.filter(is_current=False, status='review').exists()):
                status, issue = 'review', 'late_payment_requires_refund_review'
            else:
                attempt.bank_transaction = bank_id
                status = 'paid'
                order.status = 'received'
                OrderStatusEvent.objects.create(order=order, status='received')
        elif record.get('status') in {'FAILED', 'CANCELLED', 'CANCEL'} and status != 'review':
            status = 'failed' if record['status'] == 'FAILED' else 'cancelled'
    if expired and status not in {'paid', 'review', 'failed', 'cancelled'}:
        status = 'expired'
    if status in {'failed', 'cancelled', 'expired'} or (expired and status == 'review'):
        release(order)
        if order.status == 'awaiting_payment':
            order.status = 'cancelled'
            OrderStatusEvent.objects.create(order=order, status='cancelled')
    attempt.status, attempt.issue, attempt.checked_at = status, issue, timezone.now()
    attempt.save(update_fields=['status', 'issue', 'checked_at', 'bank_transaction'])
    order.payment_status = 'pending' if status in {'created', 'initiating'} else status
    order.save(update_fields=['payment_status', 'status', 'inventory_released'])
    return order.payment_status


@transaction.atomic
def retry_payment(attempt_id, user):
    """New provider transaction on the same order, only after verified closure.

    The old attempt ID is the retry idempotency key. Ambiguous/expired sessions
    are never replaced until the provider confirms a terminal failure.
    """
    from datetime import timedelta
    from django.core.exceptions import ValidationError
    from .services import coupon_amount
    old = PaymentAttempt.objects.get(pk=attempt_id, order__user=user)
    if old.provider != 'sslcommerz':
        raise ValidationError('Contact the store to resolve this payment before paying again.')
    order = Order.objects.select_for_update().get(pk=old.order_id, user=user)
    current = PaymentAttempt.objects.select_for_update().get(order=order, is_current=True)
    if current.pk != old.pk:
        return current
    if (current.status not in {'failed', 'cancelled'} or not order.inventory_released
            or order.payment_status not in {'failed', 'cancelled'} or order.status != 'cancelled'
            or current.issue or not current.checked_at
            or current.checked_at < timezone.now() - timedelta(minutes=1)):
        raise ValidationError('Payment is not safely closed. Check its status or contact support before retrying.')
    if not method_ready(order.payment_method):
        raise ValidationError('This payment method is currently unavailable. Contact the store.')
    if order.coupon_code:
        coupon = Coupon.objects.select_for_update().filter(code__iexact=order.coupon_code).first()
        lines = [{'product': item.product, 'product_id': item.product_id,
                  'subtotal': item.subtotal} for item in order.items.select_related('product')]
        if not coupon or coupon_amount(coupon, lines, user) != order.coupon_discount:
            raise ValidationError('The original discount is no longer available. Contact the store to revise this order.')
        allowed = Coupon.objects.filter(pk=coupon.pk)
        if coupon.usage_limit is not None:
            allowed = allowed.filter(used_count__lt=coupon.usage_limit)
        if not allowed.update(used_count=F('used_count') + 1):
            raise ValidationError('This coupon is no longer available.')
        CouponRedemption.objects.create(coupon=coupon, user=user, order=order)
    for reservation in order.payment_reservations.order_by('pk'):
        model = ProductVariant if reservation.variant_id else Product
        pk = reservation.variant_id or reservation.product_id
        item = model.objects.select_for_update().get(pk=pk)
        if item.stock is not None and not model.objects.filter(pk=pk, stock__gte=reservation.quantity).update(
                stock=F('stock') - reservation.quantity):
            raise ValidationError('An item is out of stock. No new payment has been started.')
        if item.stock is not None:
            from .activity import record_activity
            record_activity(item, {'stock': {'before': str(item.stock), 'after': str(item.stock - reservation.quantity)}}, source=f'payment retry order {order.pk}')
    current.is_current = False
    current.save(update_fields=['is_current'])
    new = PaymentAttempt.objects.create(order=order, amount=order.total_price,
                                       expires_at=timezone.now() + timedelta(minutes=30))
    order.inventory_released = False
    order.payment_status = 'pending'
    order.status = 'awaiting_payment'
    order.save(update_fields=['inventory_released', 'payment_status', 'status'])
    OrderStatusEvent.objects.create(order=order, status='awaiting_payment')
    return new

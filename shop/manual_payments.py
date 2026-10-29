"""Manual review uses the existing order, attempt, and inventory lifecycle."""
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from .models import Order, PaymentAttempt, ManualPaymentClaim, ManualPaymentAudit, OrderStatusEvent
from .payments import release


@transaction.atomic
def submit_reference(attempt_id, user, reference):
    from .services import settings_for_store
    from .forms import ManualReferenceForm
    form = ManualReferenceForm({'reference': reference})
    if not form.is_valid():
        raise ValidationError('Enter a valid transaction reference from your receipt.')
    attempt = PaymentAttempt.objects.get(pk=attempt_id, order__user=user)
    order = Order.objects.select_for_update().get(pk=attempt.order_id, user=user)
    attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
    existing = ManualPaymentClaim.objects.filter(attempt=attempt).first()
    if existing:
        if existing.reference == form.cleaned_data['reference']:
            return existing
        raise ValidationError('A reference has already been submitted. Contact support to correct it.')
    store = settings_for_store()
    if (attempt.provider != 'manual_bkash' or not attempt.is_current or not store.manual_bkash_ready
            or store.bkash_number != attempt.manual_receiver or attempt.expires_at <= timezone.now()
            or order.inventory_released or order.payment_status != 'pending'):
        raise ValidationError('This payment can no longer accept a reference. Contact support before paying.')
    if (ManualPaymentClaim.objects.filter(reference=form.cleaned_data['reference']).exists()
            or Order.objects.filter(payment_method='BKASH', trx_id__iexact=form.cleaned_data['reference']).exclude(pk=order.pk).exists()):
        raise ValidationError('This reference cannot be used. Contact support.')
    claim = ManualPaymentClaim.objects.create(attempt=attempt, reference=form.cleaned_data['reference'])
    ManualPaymentAudit.objects.create(claim=claim, actor=user, action='submitted', note='Customer reference claim; no payment verified.')
    attempt.status = 'review'
    attempt.issue = 'manual_reference_submitted'
    attempt.save(update_fields=['status', 'issue'])
    order.payment_status = 'manual_review'
    order.trx_id = claim.reference
    order.save(update_fields=['payment_status', 'trx_id'])
    return claim


@transaction.atomic
def review_reference(claim_id, actor, decision, note):
    if not (actor.is_active and actor.is_staff and actor.has_perm('shop.change_order')
            and actor.has_perm('shop.verify_manual_payment')):
        raise PermissionDenied
    if decision not in {'confirmed', 'rejected'} or len(note.strip()) < 10:
        raise ValidationError('Record a verification or rejection note of at least 10 characters.')
    claim = ManualPaymentClaim.objects.select_related('attempt').get(pk=claim_id)
    order = Order.objects.select_for_update().get(pk=claim.attempt.order_id)
    attempt = PaymentAttempt.objects.select_for_update().get(pk=claim.attempt_id)
    claim = ManualPaymentClaim.objects.select_for_update().get(pk=claim_id)
    if claim.status != 'awaiting':
        if claim.status == decision:
            return claim
        raise ValidationError('This claim was already reviewed. Contact the payment administrator.')
    if attempt.provider != 'manual_bkash' or not attempt.is_current:
        raise ValidationError('Only the current manual payment can be reviewed here.')
    if decision == 'confirmed':
        if (order.inventory_released or attempt.expires_at <= timezone.now()
                or order.status != 'awaiting_payment' or order.payment_status != 'manual_review'
                or attempt.amount != order.total_price or attempt.currency != 'BDT'):
            raise ValidationError('Stock reservation or amount is no longer valid. Reconcile/refund this payment; do not fulfill automatically.')
        attempt.status = 'paid'
        attempt.bank_transaction = 'manual-bkash:' + claim.reference
        order.payment_status = 'paid'
        order.status = 'received'
        OrderStatusEvent.objects.create(order=order, status='received')
    else:
        release(order)
        attempt.status = 'failed'
        order.payment_status = 'failed'
        order.status = 'cancelled'
        OrderStatusEvent.objects.create(order=order, status='cancelled')
    attempt.issue = ''
    attempt.checked_at = timezone.now()
    attempt.save(update_fields=['status', 'bank_transaction', 'issue', 'checked_at'])
    order.save(update_fields=['payment_status', 'status', 'inventory_released'])
    claim.status = decision
    claim.save(update_fields=['status'])
    ManualPaymentAudit.objects.create(claim=claim, actor=actor, action=decision, note=note.strip())
    return claim

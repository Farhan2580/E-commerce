"""Payment metadata only. Provider payloads and payment instrument data are never persisted."""
import uuid
import secrets
from django.db import models
from .models import Order, Product, ProductVariant


def transaction_id():
    return secrets.token_hex(15)


class PaymentAttempt(models.Model):
    provider = models.CharField(max_length=20, default='sslcommerz', choices=[('sslcommerz', 'SSLCOMMERZ'), ('manual_bkash', 'Manual bKash review')])
    manual_receiver = models.CharField(max_length=20, blank=True, editable=False)
    manual_instructions = models.TextField(blank=True, editable=False)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=30, unique=True, default=transaction_id, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payment_attempts')
    is_current = models.BooleanField(default=True, editable=False)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='BDT')
    status = models.CharField(max_length=20, default='created', choices=[
        (s, s.replace('_', ' ').title()) for s in
        ('created', 'initiating', 'pending', 'paid', 'failed', 'cancelled', 'expired', 'review')])
    session_key = models.CharField(max_length=200, blank=True, editable=False)
    checkout_url = models.URLField(max_length=2000, blank=True, editable=False)
    bank_transaction = models.CharField(max_length=200, null=True, blank=True, unique=True, editable=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(null=True, editable=False)
    issue = models.CharField(max_length=80, blank=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order'], condition=models.Q(is_current=True),
                                               name='one_current_payment_per_order')]


class PaymentReservation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payment_reservations')
    product = models.ForeignKey(Product, null=True, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()


class ManualPaymentClaim(models.Model):
    attempt = models.OneToOneField(PaymentAttempt, on_delete=models.PROTECT, related_name='manual_claim')
    reference = models.CharField(max_length=30, unique=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='awaiting', choices=[('awaiting', 'Awaiting verification'), ('confirmed', 'Verified against merchant records'), ('rejected', 'Rejected')])


class ManualPaymentAudit(models.Model):
    claim = models.ForeignKey(ManualPaymentClaim, on_delete=models.PROTECT, related_name='audit_events')
    actor = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=[('submitted', 'Reference submitted'), ('confirmed', 'Payment verified'), ('rejected', 'Reference rejected')])
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

"""Store-curated shopping data and private customer workflows."""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class ProductPurpose(models.Model):
    PURPOSES = [('gaming', 'Gaming'), ('camera', 'Camera'), ('study', 'Study'), ('work', 'Work')]
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE, related_name='purposes')
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    reason = models.CharField(max_length=300, help_text='Explain suitability using verified specifications.')
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['product', 'purpose'], name='unique_product_purpose')]

    def __str__(self):
        return f'{self.product} / {self.get_purpose_display()}'


class Compatibility(models.Model):
    device = models.ForeignKey('shop.Product', on_delete=models.CASCADE, related_name='accessory_matches')
    accessory = models.ForeignKey('shop.Product', on_delete=models.CASCADE, related_name='device_matches')
    compatible = models.BooleanField(default=True)
    verified = models.BooleanField(default=False, help_text='Verify only when this result applies to every listed variant of both products. Leave unverified if option-dependent.')
    evidence = models.TextField(help_text='Manufacturer reference or store-tested details supporting the result for all listed variants.')
    bought_together = models.BooleanField(default=False, help_text='Show as a curated compatible pairing; no sales-frequency claim is implied.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'accessory'], name='unique_device_accessory')]

    def clean(self):
        if self.device_id == self.accessory_id:
            raise ValidationError('Choose two different products.')
        if self.verified and not self.evidence.strip():
            raise ValidationError({'evidence': 'Provide evidence before verifying compatibility.'})

    def __str__(self):
        return f'{self.device} / {self.accessory}'


class PriceAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='price_alerts')
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey('shop.ProductVariant', null=True, blank=True, on_delete=models.CASCADE)
    target_price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    email = models.EmailField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True, editable=False)
    email_sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'product'], condition=models.Q(variant__isnull=True), name='one_product_price_alert'),
            models.UniqueConstraint(fields=['user', 'variant'], condition=models.Q(variant__isnull=False), name='one_variant_price_alert')]

    def clean(self):
        if self.variant_id and self.variant.product_id != self.product_id:
            raise ValidationError({'variant': 'Choose a variant of this product.'})
        if self.product_id and self.product.variants.exists() and not self.variant_id:
            raise ValidationError({'variant': 'Select an exact variant to monitor.'})


class CustomerNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shopping_notifications')
    key = models.CharField(max_length=150, unique=True)
    title = models.CharField(max_length=250)
    message = models.TextField()
    product = models.ForeignKey('shop.Product', null=True, blank=True, on_delete=models.SET_NULL)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class ServiceClaim(models.Model):
    STATUSES = [('submitted', 'Submitted'), ('reviewing', 'Under review'), ('approved', 'Approved'),
                ('received', 'Item received'), ('servicing', 'Servicing'), ('resolved', 'Resolved'), ('rejected', 'Rejected')]
    order = models.ForeignKey('shop.Order', on_delete=models.PROTECT, related_name='service_claims')
    item = models.ForeignKey('shop.OrderItem', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=[('return', 'Return'), ('warranty', 'Warranty')])
    reason = models.TextField(max_length=3000)
    status = models.CharField(max_length=20, choices=STATUSES, default='submitted')
    customer_update = models.TextField(blank=True, help_text='Visible to the customer. Keep internal notes out.')
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['item', 'kind'], condition=~models.Q(status__in=['resolved', 'rejected']), name='one_open_item_claim')]

    def clean(self):
        if self.item_id and self.item.order_id != self.order_id:
            raise ValidationError({'item': 'This item belongs to another order.'})

    def __str__(self):
        return f'#{self.pk} {self.get_kind_display()} / Order {self.order_id}'


class ClaimEvent(models.Model):
    claim = models.ForeignKey(ServiceClaim, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, choices=ServiceClaim.STATUSES)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class RefundRecord(models.Model):
    order = models.ForeignKey('shop.Order', on_delete=models.PROTECT, related_name='refund_records')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reference = models.CharField(max_length=150, unique=True, help_text='Actual completed refund reference from merchant records.')
    note = models.TextField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.order_id or self.amount is None:
            return
        from django.db.models import Sum
        total = RefundRecord.objects.filter(order_id=self.order_id).exclude(pk=self.pk).aggregate(value=Sum('amount'))['value'] or Decimal('0')
        if self.order.payment_status != 'paid' or total + self.amount > self.order.total_price:
            raise ValidationError('Refunds require a paid order and cannot exceed its collected total.')


class CatalogActivity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    model = models.CharField(max_length=60)
    object_id = models.CharField(max_length=60)
    label = models.CharField(max_length=250)
    changes = models.JSONField(default=dict)
    source = models.CharField(max_length=100, default='application')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

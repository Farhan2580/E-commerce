"""Attribute catalog edits to the current request; do not record customer secrets."""
from contextvars import ContextVar
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Product, ProductVariant, Order, Preorder, CatalogActivity, ServiceClaim, ClaimEvent

current_actor = ContextVar('catalog_actor', default=None)
current_source = ContextVar('catalog_source', default='application')


class ActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = current_actor.set(request.user.pk if request.user.is_authenticated else None)
        source = current_source.set('admin' if request.path.startswith('/admin/') else 'storefront')
        try:
            return self.get_response(request)
        finally:
            current_actor.reset(actor)
            current_source.reset(source)


def record_activity(obj, changes, source=None):
    if changes:
        CatalogActivity.objects.create(actor_id=current_actor.get(), model=obj._meta.label,
            object_id=str(obj.pk), label=str(obj)[:250], changes=changes, source=source or current_source.get())


TRACKED = {Product: ('price', 'stock'), ProductVariant: ('price', 'stock'), Order: ('status',),
           Preorder: ('status', 'advance_amount', 'advance_status', 'estimated_arrival')}


@receiver(pre_save)
def capture_changes(sender, instance, raw=False, using=None, update_fields=None, **kwargs):
    if raw or sender not in TRACKED or not instance.pk:
        return
    fields = [field for field in TRACKED[sender] if update_fields is None or field in update_fields]
    old = sender.objects.using(using).filter(pk=instance.pk).values(*fields).first() if fields else None
    normalized = {field: sender._meta.get_field(field).to_python(getattr(instance, field)) for field in fields}
    instance._catalog_changes = {field: {'before': str(old[field]), 'after': str(normalized[field])}
                                 for field in fields if old and old[field] != normalized[field]}


@receiver(post_save)
def log_changes(sender, instance, raw=False, **kwargs):
    if not raw and sender in TRACKED:
        record_activity(instance, getattr(instance, '_catalog_changes', {}))


@receiver(pre_save, sender=ServiceClaim)
def capture_claim(sender, instance, raw=False, **kwargs):
    if not raw and instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._claim_changed = old and (old.status != instance.status or old.customer_update != instance.customer_update)


@receiver(post_save, sender=ServiceClaim)
def claim_event(sender, instance, created=False, raw=False, **kwargs):
    if not raw and not created and getattr(instance, '_claim_changed', False):
        ClaimEvent.objects.create(claim=instance, status=instance.status, message=instance.customer_update)
        record_activity(instance, {'status': {'after': instance.status}}, source='service claim')

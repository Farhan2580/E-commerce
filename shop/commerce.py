"""Delivery quotes, private guest access and catalog-driven PC compatibility."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import DeliveryZone, Order, PCComponent


def selected_zone(value, required=False, lock=False):
    zones = DeliveryZone.objects.filter(active=True)
    if lock:
        zones = zones.select_for_update()
    if not value:
        if required and zones.exists():
            raise ValidationError('Choose a delivery area to confirm the delivery charge.')
        return None
    pk = getattr(value, 'pk', value)
    zone = zones.filter(pk=pk).first() if str(pk).isdigit() else None
    if not zone:
        raise ValidationError('This delivery area is unavailable. Choose another area.')
    return zone


def remember_guest_order(request, order):
    if order.user_id is None:
        ids = request.session.get('guest_order_ids', [])
        request.session['guest_order_ids'] = list(dict.fromkeys([*ids, order.pk]))[-50:]


def accessible_orders(request):
    # Knowing an order ID, phone number or email never grants access.
    ids = [value for value in request.session.get('guest_order_ids', []) if type(value) is int][:50]
    rule = Q(user__isnull=True, pk__in=ids)
    if request.user.is_authenticated:
        rule |= Q(user=request.user)
    return Order.objects.filter(rule)


def owned_order(request, pk):
    return get_object_or_404(accessible_orders(request).prefetch_related('items', 'status_events'), pk=pk)


def order_progress(order):
    stages = [('received', 'Received'), ('confirmed', 'Confirmed'), ('processing', 'Preparing'),
              ('packed', 'Packed'), ('shipped', 'Shipped'), ('delivered', 'Delivered')]
    current = next((index for index, (code, _) in enumerate(stages) if code == order.status), -1)
    return [{'label': label, 'current': index == current, 'complete': 0 <= index < current}
            for index, (_, label) in enumerate(stages)]


REQUIRED_PARTS = {'cpu', 'motherboard', 'ram', 'storage', 'psu', 'case'}


def pc_build(data):
    profiles = list(PCComponent.objects.filter(active=True).select_related('product').prefetch_related('product__variants'))
    slots, chosen, errors, warnings, checks = [], {}, [], [], []
    total = Decimal('0')
    for kind, label in PCComponent.KINDS:
        options = []
        for profile in profiles:
            if profile.kind != kind:
                continue
            product = profile.product
            for item in list(product.variants.all()) or [product]:
                variant = item if item is not product else None
                options.append({'key': f'{product.pk}:{variant.pk}' if variant else str(product.pk),
                                'product': product, 'variant': variant, 'profile': profile,
                                'name': f'{product.name} · {variant.name}' if variant else product.name,
                                'price': item.price, 'available': item.stock is None or item.stock > 0})
        key = str(data.get(kind, ''))
        selection = next((option for option in options if option['key'] == key), None)
        if key and not selection:
            errors.append(f'{label}: the selected component is no longer available.')
        if selection:
            chosen[kind] = selection
            total += selection['price']
            if not selection['available']:
                errors.append(f'{label}: this option is out of stock.')
        slots.append({'kind': kind, 'label': label, 'required': kind in REQUIRED_PARTS,
                      'options': options, 'selected': key, 'selection': selection})
    def profile(kind):
        return chosen[kind]['profile'] if kind in chosen else None
    def match(left, right, field, label, right_field=None, multiple=False):
        a, b = profile(left), profile(right)
        if a and b:
            av, bv = getattr(a, field), getattr(b, right_field or field)
            if not av or not bv:
                warnings.append(f'{label}: specifications need confirmation.')
            else:
                av = str(av).strip().casefold()
                values = [str(v).strip().casefold() for v in bv] if multiple else [str(bv).strip().casefold()]
                if av not in values:
                    errors.append(f'{label}: the selected components do not match.')
                else:
                    checks.append(f'{label} matches')
    match('cpu', 'motherboard', 'socket', 'CPU socket')
    match('ram', 'motherboard', 'memory_type', 'Memory generation')
    match('motherboard', 'case', 'form_factor', 'Case motherboard size', 'supported_form_factors', True)
    match('storage', 'motherboard', 'storage_interface', 'Storage interface', 'supported_storage_interfaces', True)
    match('cpu', 'cooler', 'socket', 'Cooler socket', 'supported_sockets', True)
    cpu, gpu, psu = profile('cpu'), profile('gpu'), profile('psu')
    if cpu and not gpu:
        if cpu.integrated_graphics is False:
            errors.append('This CPU needs a separate graphics card. Choose a graphics card.')
        elif cpu.integrated_graphics is None:
            warnings.append('CPU integrated graphics needs confirmation if no graphics card is selected.')
    if psu and cpu:
        if gpu and gpu.minimum_psu_watts and psu.power_watts and psu.power_watts < gpu.minimum_psu_watts:
            errors.append(f'Graphics card requires a PSU rated at least {gpu.minimum_psu_watts} W.')
        power = [cpu.power_watts] + ([gpu.power_watts] if gpu else [])
        if psu.power_watts and all(value is not None for value in power):
            required = max(sum(power) + 100, (gpu.minimum_psu_watts or 0) if gpu else 0)
            if psu.power_watts < required:
                errors.append(f'Power supply: choose at least {required} W for the recorded power estimates.')
            else:
                checks.append(f'PSU meets the recorded {required} W estimate')
        else:
            warnings.append('Power supply sizing needs confirmation.')
    missing = [label for kind, label in PCComponent.KINDS if kind in REQUIRED_PARTS and kind not in chosen]
    if chosen:
        warnings.append('Confirm BIOS support, memory capacity, cooling, physical clearances and power connectors with the store before ordering.')
    return {'slots': slots, 'chosen': chosen, 'total': total, 'errors': errors, 'warnings': warnings,
            'checks': checks, 'missing': missing, 'count': len(chosen), 'can_add': not errors and not missing,
            'has_components': bool(profiles)}

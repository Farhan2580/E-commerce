"""Collection presentation and filter choices derived from existing catalog data."""
from collections import defaultdict
from django.db.models import Q
from django.urls import reverse
from .models import NavigationItem, ProductVariant, Brand

SPEC_LABELS = {
    'model': 'Model', 'ram': 'RAM', 'processor': 'Processor', 'generation': 'Generation',
    'network': 'Network', 'region': 'Region', 'sim': 'SIM', 'type': 'Type',
    'edition': 'Edition', 'plug': 'Plug', 'storage': 'Storage', 'size': 'Size',
    'color': 'Color', 'body': 'Body', 'warranty': 'Warranty',
}


def catalog_facets(scope, params):
    facets = []
    for field in ('storage', 'ram', 'color', 'size', 'warranty'):
        values = list(ProductVariant.objects.filter(product__in=scope.values('pk')).exclude(
            **{field: ''}).order_by(field).values_list(field, flat=True).distinct())
        if values:
            selected = params.getlist('option_' + field)[:50]
            facets.append({'label': SPEC_LABELS.get(field, field.title()), 'param': 'option_' + field, 'variant': field,
                           'options': [{'value': v, 'checked': v in selected} for v in values]})
    specs = defaultdict(dict)
    for data in scope.prefetch_related(None).values_list('specifications', flat=True).iterator(chunk_size=500):
        if not isinstance(data, dict):
            continue
        for key, value in data.items():
            normalized = key.strip().casefold()
            if normalized not in SPEC_LABELS or isinstance(value, (dict, list, bool)) or value is None:
                continue
            if str(value).strip():
                values = specs[normalized].setdefault(str(value), [])
                if (key, value) not in values:
                    values.append((key, value))
    for key in SPEC_LABELS:
        if key not in specs:
            continue
        selected = params.getlist('spec_' + key)[:50]
        facets.append({'label': SPEC_LABELS[key], 'param': 'spec_' + key, 'spec': specs[key],
                       'options': [{'value': v, 'checked': v in selected} for v in sorted(specs[key], key=str.casefold)]})
    return facets


def apply_facets(products, facets, params):
    variant_filters = {}
    for facet in facets:
        chosen = params.getlist(facet['param'])[:50]
        if not chosen:
            continue
        allowed = {option['value'] for option in facet['options']}
        if any(value not in allowed for value in chosen):
            return products.none()
        if 'variant' in facet:
            variant_filters['variants__' + facet['variant'] + '__in'] = chosen
        else:
            condition = Q()
            for value in chosen:
                for key, raw in facet['spec'][value]:
                    condition |= Q(**{'specifications__' + key: raw})
            products = products.filter(condition)
    if variant_filters:
        # One joined variant must satisfy all selected option dimensions.
        products = products.filter(**variant_filters)
    known = {facet['param'] for facet in facets}
    if any((key.startswith('option_') or key.startswith('spec_')) and key not in known for key in params):
        return products.none()
    return products


def collection_presentation(request, selected, scope):
    brand_value = request.GET.get('brand', '')
    brand = Brand.objects.filter(pk=brand_value).first() if brand_value.isdigit() else None
    items = list(NavigationItem.objects.filter(visible=True).select_related('category', 'brand'))
    item = next((item for item in items if item.category_id == (selected.pk if selected else None)
                 and item.brand_id == (brand.pk if brand else None)), None)
    if item is None and selected:
        item = next((item for item in items if item.category_id == selected.pk and not item.brand_id), None)
    if item is None and brand:
        item = next((item for item in items if item.brand_id == brand.pk and not item.category_id), None)
    label = item.label if item else (selected.name if selected else (brand.name if brand else 'All Products'))
    params = request.GET.copy()
    for key in list(params):
        if key not in {'category', 'brand', 'offer'}:
            params.pop(key)
    title = item.page_title if item and item.page_title else label
    return {'title': title, 'label': label,
            'intro': item.introduction if item and item.introduction else f'Explore the {label} collection at GadgetFlow.',
            'banner': item.hero_image.url if item and item.hero_image else '',
            'products': list(scope.exclude(image='').filter(image__isnull=False).distinct()[:3]),
            'clear_url': reverse('product_list') + ('?' + params.urlencode() if params else '')}

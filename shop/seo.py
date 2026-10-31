"""Search metadata derived from actual catalog records, never invented ratings."""
import json
from django.urls import reverse


def safe_json_ld(value):
    # JSON in a script element must not let user-controlled text close that element.
    return json.dumps(value, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def product_schema(request, product, reviews):
    canonical = request.build_absolute_uri(reverse('product_detail', args=[product.pk]))
    result = {'@context': 'https://schema.org', '@type': 'Product', 'name': product.name,
              'url': canonical, 'description': product.description[:5000]}
    if product.image:
        result['image'] = request.build_absolute_uri(product.image.url)
    if product.brand:
        result['brand'] = {'@type': 'Brand', 'name': product.brand.name}
    variants = list(product.variants.all())
    if variants:
        result.update({'@type': 'ProductGroup', 'productGroupID': f'gf-{product.pk}', 'hasVariant': []})
        dimensions = []
        for field in ['color', 'size']:
            if any(getattr(item, field) for item in variants):
                dimensions.append('https://schema.org/' + field)
        if any(item.storage for item in variants):
            dimensions.append('Storage')
        if dimensions:
            result['variesBy'] = dimensions
        for item in variants:
            variant = {'@type': 'Product', 'name': f'{product.name} · {item.name}', 'url': canonical,
                       'offers': {'@type': 'Offer', 'priceCurrency': 'BDT', 'price': str(item.price), 'url': canonical,
                                  'availability': 'https://schema.org/InStock' if item.stock > 0 else 'https://schema.org/OutOfStock'}}
            image = item.image or product.image
            if image:
                variant['image'] = request.build_absolute_uri(image.url)
            if item.sku:
                variant['sku'] = item.sku
            for field in ['color', 'size']:
                if getattr(item, field):
                    variant[field] = getattr(item, field)
            if item.storage:
                variant['additionalProperty'] = {'@type': 'PropertyValue', 'name': 'Storage', 'value': item.storage}
            result['hasVariant'].append(variant)
    else:
        offer = {'@type': 'Offer', 'priceCurrency': 'BDT', 'price': str(product.price), 'url': canonical}
        if product.stock is not None:
            offer['availability'] = 'https://schema.org/InStock' if product.stock > 0 else 'https://schema.org/OutOfStock'
        result['offers'] = offer
    entries = list(reviews)
    if entries:
        result['aggregateRating'] = {'@type': 'AggregateRating', 'ratingValue': round(sum(item.rating for item in entries) / len(entries), 2),
                                     'reviewCount': len(entries)}
    return result

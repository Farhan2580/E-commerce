def navigation_categories():
    from types import SimpleNamespace
    from django.urls import reverse
    from urllib.parse import urlencode
    from .models import Category, Product, NavigationItem
    categories = list(Category.objects.prefetch_related('children'))
    by_id = {category.pk: category for category in categories}
    roots = [category for category in categories if category.parent_id is None]
    brand_sets = {category.pk: {} for category in categories}
    product_brands = list(Product.objects.filter(brand__isnull=False).values_list(
            'category_id', 'brand_id', 'brand__name').distinct())
    for category_id, brand_id, name in product_brands:
        seen = set()
        current = by_id.get(category_id)
        while current and current.pk not in seen:
            seen.add(current.pk)
            if current.pk in brand_sets:
                brand_sets[current.pk][brand_id] = name
            current = by_id.get(current.parent_id)
    for category in categories:
        category.nav_url = reverse('product_list') + '?' + urlencode({'category': category.pk})
        category.nav_brands = [
            {'name': name, 'url': reverse('product_list') + '?' + urlencode({'category': category.pk, 'brand': pk})}
            for pk, name in sorted(brand_sets[category.pk].items(), key=lambda item: (item[1].casefold(), item[0]))]
    configured = list(NavigationItem.objects.select_related('category', 'brand'))
    if not configured:
        return roots
    result = []
    for item in configured:
        if not item.visible or not (item.category_id or item.brand_id):
            continue
        filters = {}
        if item.category_id:
            filters['category'] = item.category_id
        if item.brand_id:
            filters['brand'] = item.brand_id
        category = by_id.get(item.category_id)
        options = category.nav_brands if category and not item.brand_id else []
        children = category.children if category else SimpleNamespace(all=[])
        if item.brand_id and not category:
            ids = {pk for pk, brand_pk, _ in product_brands if brand_pk == item.brand_id}
            options = [{'name': cat.name, 'url': reverse('product_list') + '?' + urlencode({'category': cat.pk, 'brand': item.brand_id})}
                       for cat in categories if cat.pk in ids]
        result.append(SimpleNamespace(name=item.label, pk=item.category_id, nav_url=reverse('product_list') + '?' + urlencode(filters),
                                      nav_brands=options, children=children))
    return result


def cart_count(request):
    from django.conf import settings
    from .services import comparison_ids, normalized_cart, settings_for_store
    from .models import Category, Wishlist
    from .support import support_context
    store = settings_for_store()
    return {'commerce_preview': getattr(settings, 'COMMERCE_PREVIEW', False),
            'cart_count': sum(normalized_cart(request.session).values()),
            'nav_categories': navigation_categories(),
            **support_context(request, store),
            'compare_ids': comparison_ids(request.session),
            'wishlist_ids': set(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
            if request.user.is_authenticated else set()}

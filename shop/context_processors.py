def cart_count(request):
    from .services import comparison_ids, normalized_cart, settings_for_store
    from .models import Category, Wishlist
    from .support import support_context
    store = settings_for_store()
    return {'cart_count': sum(normalized_cart(request.session).values()),
            'nav_categories': Category.objects.filter(parent__isnull=True).prefetch_related('children'),
            **support_context(request, store),
            'compare_ids': comparison_ids(request.session),
            'wishlist_ids': set(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
            if request.user.is_authenticated else set()}

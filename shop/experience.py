def warranty_label(product):
    from .models import ProductWarranty
    try:
        warranty = product.warranty
    except ProductWarranty.DoesNotExist:
        return 'Not confirmed'
    if not warranty.is_verified:
        return 'Not confirmed'
    return ' · '.join(value for value in (warranty.get_warranty_type_display(), warranty.period_en) if value)

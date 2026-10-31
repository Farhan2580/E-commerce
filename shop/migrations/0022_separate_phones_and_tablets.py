"""Keep the original category URL while separating the mobile device catalog."""
import re

from django.db import migrations


def separate_devices(apps, schema_editor):
    alias = schema_editor.connection.alias
    Category = apps.get_model('shop', 'Category')
    Product = apps.get_model('shop', 'Product')
    Navigation = apps.get_model('shop', 'NavigationItem')
    Section = apps.get_model('shop', 'HomeSection')
    legacy = Category.objects.using(alias).filter(name__iexact='Phones & Tablets').first()
    if legacy is None:
        return

    combined_links = {
        name: list(apps.get_model('shop', name).objects.using(alias).filter(
            categories=legacy).values_list('pk', flat=True))
        for name in ('Coupon', 'FooterGroup')
    }

    # Reuse the combined category's ID, image and display order for existing links.
    existing = Category.objects.using(alias).filter(name__iexact='Phones').first()
    tablets, _ = Category.objects.using(alias).get_or_create(
        name='Tablets', defaults={'featured': legacy.featured, 'position': legacy.position + 1})
    if existing:
        Product.objects.using(alias).filter(category_id=existing.pk).update(category_id=legacy.pk)
        Navigation.objects.using(alias).filter(category_id=existing.pk).update(category_id=legacy.pk)
        Section.objects.using(alias).filter(category_id=existing.pk).update(category_id=legacy.pk)
        Category.objects.using(alias).filter(parent_id=existing.pk).exclude(pk=legacy.pk).update(parent_id=legacy.pk)
        if legacy.parent_id == existing.pk:
            legacy.parent_id = existing.parent_id
        for model_name in ('Coupon', 'FooterGroup'):
            Model = apps.get_model('shop', model_name)
            for obj in Model.objects.using(alias).filter(categories=existing):
                obj.categories.add(legacy)
        existing.delete(using=alias)

    legacy.name = 'Phones'
    legacy.save(using=alias, update_fields=['name', 'parent'])
    tablets.refresh_from_db(using=alias)
    # Tablet categories must not be descendants of Phones, which includes children.
    if tablets.parent_id == legacy.pk:
        tablets.parent_id = legacy.parent_id
    tablets.featured = tablets.featured or legacy.featured
    tablets.save(using=alias, update_fields=['parent', 'featured'])

    # Only explicit tablet names/types are moved; other legacy products retain
    # their original category ID. No product, image, variant or order is recreated.
    tablet_name = re.compile(r'\b(?:ipad\w*|tablets?|galaxy\s+tab\w*|surface\s+(?:pro|go)|'
                             r'matepad\w*|mediapad\w*|(?:xiaomi|redmi|oneplus|lenovo)\s+pad\w*)\b', re.I)
    for product in Product.objects.using(alias).filter(category_id=legacy.pk).iterator():
        specs = product.specifications if isinstance(product.specifications, dict) else {}
        device_type = next((str(value).casefold() for key, value in specs.items()
                            if key.strip().casefold() in {'type', 'device type'}), '')
        if tablet_name.search(product.name) or device_type in {'tablet', 'tablets'}:
            Product.objects.using(alias).filter(pk=product.pk).update(category_id=tablets.pk)

    # Preserve the scope of promotions and footer links previously covering both.
    for model_name in ('Coupon', 'FooterGroup'):
        Model = apps.get_model('shop', model_name)
        for obj in Model.objects.using(alias).filter(pk__in=combined_links[model_name]):
            obj.categories.add(tablets)
    Section.objects.using(alias).filter(category_id=legacy.pk, title='Phones & Tablets').update(title='Phones')
    for label, category, position in [('Phones', legacy, 1), ('Tablets', tablets, 2)]:
        items = Navigation.objects.using(alias).filter(label__iexact=label, brand__isnull=True)
        if items.exists():
            items.update(category_id=category.pk)
        else:
            Navigation.objects.using(alias).create(label=label, category_id=category.pk, position=position)
    Navigation.objects.using(alias).filter(label='Phones & Tablets', category_id=legacy.pk).update(label='Phones')


class Migration(migrations.Migration):
    dependencies = [('shop', '0021_shopping_experience')]
    operations = [migrations.RunPython(separate_devices)]

from django.db import migrations


def seed_storefront(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    Order = apps.get_model('shop', 'Order')
    Item = apps.get_model('shop', 'OrderItem')
    Banner = apps.get_model('shop', 'Banner')
    Brand = apps.get_model('shop', 'Brand')
    Section = apps.get_model('shop', 'HomeSection')
    Placement = apps.get_model('shop', 'SectionProduct')
    Settings = apps.get_model('shop', 'StoreSettings')
    alias = schema_editor.connection.alias
    Settings.objects.using(alias).get_or_create(pk=1, defaults={'name': 'GadgetFlow'})
    for item in Item.objects.using(alias).select_related('product').all():
        if item.product:
            item.product_name = item.product.name
            item.save(using=alias, update_fields=['product_name'])
    for order in Order.objects.using(alias).all():
        order.subtotal = order.total_price
        order.save(using=alias, update_fields=['subtotal'])
    products = list(Product.objects.using(alias).order_by('pk'))
    # Only identify explicit, recognisable names already present in the catalog.
    names = [('iphone', 'Apple'), ('ipad', 'Apple'), ('apple', 'Apple'), ('asus', 'ASUS'),
             ('galaxy', 'Samsung'), ('sony', 'Sony'), ('joyroom', 'Joyroom'),
             ('lg ', 'LG'), ('yamaha', 'Yamaha'), ('royal enfield', 'Royal Enfield')]
    for product in products:
        for text, name in names:
            if text in product.name.lower():
                brand, _ = Brand.objects.using(alias).get_or_create(name=name)
                product.brand = brand
                product.save(using=alias, update_fields=['brand'])
                break
    for i, product in enumerate([p for p in products if p.image][:3]):
        Banner.objects.using(alias).create(title=product.name,
            description='Explore the collection at GadgetFlow.', product=product,
            link=f'/product/{product.pk}/', position=i)
    section = Section.objects.using(alias).create(title='Featured products', position=0)
    for i, product in enumerate(products[:10]):
        Placement.objects.using(alias).create(section=section, product=product, position=i)
    Category = apps.get_model('shop', 'Category')
    for i, category in enumerate(Category.objects.using(alias).filter(name__in=['Phones & Tablets', 'Laptop', 'Sound Equipment'])):
        Section.objects.using(alias).create(title=category.name, category=category, position=i + 1)


class Migration(migrations.Migration):
    dependencies = [('shop', '0002_storefront_catalog_and_checkout')]
    operations = [migrations.RunPython(seed_storefront, migrations.RunPython.noop)]

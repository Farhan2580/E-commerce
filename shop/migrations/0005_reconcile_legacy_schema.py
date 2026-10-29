from django.db import migrations


def reconcile_legacy_schema(apps, schema_editor):
    connection = schema_editor.connection
    Product = apps.get_model('shop', 'Product')
    with connection.cursor() as cursor:
        columns = {field.name for field in connection.introspection.get_table_description(cursor, Product._meta.db_table)}
    if 'logo' not in columns:
        schema_editor.add_field(Product, Product._meta.get_field('logo'))
    Preorder = apps.get_model('shop', 'Preorder')
    if Preorder._meta.db_table not in connection.introspection.table_names():
        schema_editor.create_model(Preorder)


class Migration(migrations.Migration):
    dependencies = [('shop', '0004_expand_order_totals')]
    operations = [migrations.RunPython(reconcile_legacy_schema, migrations.RunPython.noop)]

"""Bounded CSV preview, model validation and atomic apply with stale-row checks."""
import csv
import io
import json
from django import forms
from django.core.exceptions import ValidationError, PermissionDenied
from .models import Brand, Product, ProductVariant

SCHEMAS = {
    'brand': (Brand, ['name', 'featured', 'position']),
    'product': (Product, ['name', 'category', 'brand', 'description', 'price', 'compare_at_price', 'stock', 'featured', 'position', 'low_stock_threshold', 'specifications']),
    'variant': (ProductVariant, ['product', 'name', 'sku', 'color', 'storage', 'ram', 'size', 'warranty', 'price', 'compare_at_price', 'stock'])}


def snapshot(obj, fields):
    return {name: str(getattr(obj, name + '_id') if obj._meta.get_field(name).many_to_one else getattr(obj, name)) for name in fields}


def csv_safe(value):
    value = '' if value is None else str(value)
    return '\t' + value if value.startswith(('=', '+', '-', '@')) else value


def export_csv(kind):
    Model, fields = SCHEMAS[kind]
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['id', *fields])
    for obj in Model.objects.order_by('pk').iterator():
        row = [obj.pk]
        for field in fields:
            value = getattr(obj, field + '_id') if obj._meta.get_field(field).many_to_one else getattr(obj, field)
            row.append(csv_safe(json.dumps(value, ensure_ascii=False) if field == 'specifications' else value))
        writer.writerow(row)
    return output.getvalue()


def parse_csv(kind, upload):
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError('Use a CSV file no larger than 2 MB and 200 rows.')
    try:
        reader = csv.DictReader(io.StringIO(upload.read().decode('utf-8-sig')))
        fields = ['id', *SCHEMAS[kind][1]]
        if reader.fieldnames != fields:
            raise ValidationError('Use the exact headers and column order from an exported CSV.')
        rows = []
        for row in reader:
            if len(rows) >= 200 or None in row or any(value is None for value in row.values()):
                raise ValidationError('Use up to 200 complete rows with the exported columns.')
            rows.append({key: value[1:] if value.startswith(('\t=', '\t+', '\t-', '\t@')) else value for key, value in row.items()})
        if not rows:
            raise ValidationError('The CSV contains no data rows.')
        return rows
    except (UnicodeError, csv.Error) as exc:
        raise ValidationError('Use a valid UTF-8 CSV file.') from exc


def validate_rows(kind, rows, user, apply=False, snapshots=None):
    Model, fields = SCHEMAS[kind]
    Form = forms.modelform_factory(Model, fields=fields)
    results, seen, unique_values = [], set(), set()
    for index, row in enumerate(rows):
        pk = row.get('id', '').strip()
        action = 'change' if pk else 'add'
        if not user.has_perm(f'shop.{action}_{Model._meta.model_name}'):
            raise PermissionDenied
        objects = Model.objects.select_for_update() if apply else Model.objects
        obj = objects.filter(pk=pk).first() if pk.isdigit() else None
        errors = []
        if pk and (not pk.isdigit() or obj is None or pk in seen):
            errors.append('ID is invalid, missing, or repeated.')
        seen.add(pk) if pk else None
        current = snapshot(obj, fields) if obj else None
        if snapshots is not None and current != snapshots[index]:
            errors.append('This record changed after preview. Upload again to review the latest data.')
        form = Form(row, instance=obj)
        valid = form.is_valid()
        if kind == 'product' and valid:
            specs = form.cleaned_data.get('specifications') or {}
            if not isinstance(specs, dict) or any(not str(key).strip() or isinstance(value, (dict, list)) or value is None for key, value in specs.items()):
                form.add_error('specifications', 'Use a JSON object with nonempty labels and simple values.')
                valid = False
        errors.extend(f'{key}: {", ".join(value)}' for key, value in form.errors.items())
        proposed = snapshot(form.instance, fields) if valid else {}
        changes = [{'field': field, 'before': current[field] if current else '(new)', 'after': proposed[field]}
                   for field in fields if valid and (current is None or current[field] != proposed[field])]
        key = (row.get('product'), row.get('name')) if kind == 'variant' else row.get('name') if kind == 'brand' else None
        if key is not None:
            if key in unique_values:
                errors.append('This unique name appears more than once in the CSV.')
            unique_values.add(key)
        results.append({'row': index + 2, 'id': pk, 'name': row.get('name', ''), 'action': action,
                        'errors': errors, 'snapshot': current, 'changes': changes, 'form': form if valid else None})
    if apply:
        if any(result['errors'] for result in results):
            raise ValidationError('CSV validation changed or a row is invalid. Preview again; nothing was imported.')
        for result in results:
            result['form'].save()
    return results

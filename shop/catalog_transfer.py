"""Catalog-only snapshots and conservative, additive reconciliation.

No auth/order/payment/session/settings models are reachable through this module.
Image fields retain their original storage keys; no uploaded file is overwritten.
"""
import hashlib
import json
import re
from decimal import Decimal
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db import connection
from PIL import Image

MODEL_NAMES = ('Category', 'Brand', 'Product', 'ProductVariant', 'ProductImage',
               'Banner', 'HomeSection', 'SectionProduct')
IDENTITY = {'Category': ('name',), 'Brand': ('name',), 'Product': ('name', 'category', 'brand'),
            'ProductVariant': ('product', 'name'), 'ProductImage': ('product', 'image', 'purpose'),
            'Banner': ('title',), 'HomeSection': ('title',), 'SectionProduct': ('section', 'product')}


def plain(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f') if value else '0'
    if hasattr(value, 'name') and isinstance(value, models.fields.files.FieldFile):
        return value.name
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def model_for(name):
    if name not in MODEL_NAMES:
        raise ValueError('Only explicitly allowlisted catalog models are accepted.')
    return apps.get_model('shop', name)


def fields_for(model):
    return {f.name: f for f in model._meta.concrete_fields if not f.primary_key}


@transaction.atomic
def export_catalog():
    records = []
    for name in MODEL_NAMES:
        model = model_for(name)
        for obj in model.objects.order_by('pk').iterator(chunk_size=500):
            records.append({'model': name, 'source_id': obj.pk,
                            'fields': {key: plain(field.value_from_object(obj)) for key, field in fields_for(model).items()}})
    return {'format': 'gadgetflow-catalog-v1', 'records': records}


def ref(record):
    return f"{record['model']}:{record['source_id']}"


def safe_key(name):
    if not name:
        return
    if not isinstance(name, str) or '\\' in name or PurePosixPath(name).is_absolute() or any(
            part in {'', '.', '..'} for part in name.split('/')):
        raise ValueError('Unsafe image key in catalog bundle.')


def remap_link(link, mapping):
    """Rebase known internal IDs too; external URLs are never fetched or rewritten."""
    parts = urlsplit(link)
    if parts.username or parts.password:
        raise ValueError('Catalog links must not contain credentials.')
    if parts.netloc or parts.scheme:
        return link, []
    pending = []
    def target(model, source_id):
        key = f'{model}:{source_id}'
        if key not in mapping:
            pending.append(key)
            return source_id
        if mapping[key] is None:
            pending.append(key)
            return source_id
        return mapping[key]
    path = parts.path
    match = re.fullmatch(r'/(product|section)/(\d+)/', path)
    if match:
        model = 'Product' if match[1] == 'product' else 'HomeSection'
        path = f'/{match[1]}/{target(model, int(match[2]))}/'
    params = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if path == '/products/' and key in {'category', 'brand'} and value.isdigit():
            value = str(target('Category' if key == 'category' else 'Brand', int(value)))
        if path == '/products/' and key == 'offer' and value.isdigit():
            raise ValueError('Offer-link IDs require separate reconciliation; offers are excluded from this importer.')
        params.append((key, value))
    return urlunsplit(('', '', path, urlencode(params), parts.fragment)), pending


def validate_bundle(document):
    if document.get('format') != 'gadgetflow-catalog-v1' or not isinstance(document.get('records'), list):
        raise ValueError('Not a catalog-v1 bundle.')
    seen = set()
    for row in document['records']:
        model = model_for(row['model'])
        allowed = fields_for(model)
        if type(row['source_id']) is not int or row['source_id'] <= 0 or ref(row) in seen:
            raise ValueError('Invalid or duplicate source reference.')
        seen.add(ref(row))
        if not isinstance(row['fields'], dict) or set(row['fields']) != set(allowed):
            raise ValueError('Bundle fields differ from the current catalog schema; migrate first.')
        for key, field in allowed.items():
            if isinstance(field, models.ImageField):
                safe_key(row['fields'][key])
        if row.get('identity_changed_locally'):
            raise ValueError('A changed local identity needs explicit reconciliation, not an automatic new record.')
    # Detect ambiguous source identities before considering any target writes.
    rows = {ref(row): row for row in document['records']}
    def identity(row, visiting=()):
        if ref(row) in visiting:
            raise ValueError('Cycle in catalog identity references.')
        parts = []
        for key in IDENTITY[row['model']]:
            value = row['fields'][key]
            field = fields_for(model_for(row['model']))[key]
            if field.is_relation and value is not None:
                target = f'{field.related_model.__name__}:{value}'
                if target not in rows:
                    raise ValueError('Catalog dependency is absent from bundle.')
                value = identity(rows[target], (*visiting, ref(row)))
            parts.append(value)
        return json.dumps([row['model'], parts], sort_keys=True)
    identities = [identity(row) for row in rows.values()]
    if len(identities) != len(set(identities)):
        raise ValueError('Ambiguous natural keys in source catalog. Resolve duplicates before importing.')


def plan_catalog(document):
    validate_bundle(document)
    unresolved = list(document['records'])
    mapping, rows, creates = {}, [], []
    while unresolved:
        progress = False
        for row in unresolved[:]:
            model = model_for(row['model'])
            fields = fields_for(model)
            data, pending_keys = {}, set()
            ready = True
            for key, field in fields.items():
                value = row['fields'][key]
                if field.is_relation and value is not None:
                    dependency = f'{field.related_model.__name__}:{value}'
                    if dependency not in mapping:
                        ready = False
                        break
                    value = mapping[dependency]
                    if value is None:
                        pending_keys.add(key)
                data[field.attname] = value
            if not ready:
                continue
            if row['model'] == 'Banner':
                data['link'], link_pending = remap_link(data['link'], mapping)
                if any(key not in mapping for key in link_pending):
                    if any(key not in {ref(record) for record in document['records']} for key in link_pending):
                        raise ValueError('A banner destination refers to an absent source record.')
                    continue
                if link_pending:
                    pending_keys.add('link')
            progress = True
            unresolved.remove(row)
            lookup = {fields[key].attname: data[fields[key].attname] for key in IDENTITY[row['model']]}
            matches = [] if pending_keys.intersection(IDENTITY[row['model']]) else list(model.objects.filter(**lookup)[:2])
            if len(matches) > 1:
                raise ValueError('Ambiguous target catalog identity: ' + ref(row))
            obj = matches[0] if matches else None
            mapping[ref(row)] = obj.pk if obj else None
            changes = []
            if obj:
                changes = [key for key, field in fields.items() if key in pending_keys or
                           plain(field.value_from_object(obj)) != plain(field.to_python(data[field.attname]))]
            else:
                # Validate scalar fields and model rules without assigning source PKs.
                candidate = model(**data)
                candidate.full_clean(exclude=list(pending_keys), validate_unique=False, validate_constraints=False)
                creates.append(row)
            rows.append({'ref': ref(row), 'model': row['model'], 'target_id': obj.pk if obj else None,
                         'label': row['fields'].get('name', row['fields'].get('title', row['fields'].get('image', ''))),
                         'action': 'create' if obj is None else ('preserve_existing' if changes else 'existing_identical'),
                         'different_fields': changes})
        if not progress:
            raise ValueError('Missing or cyclic catalog dependencies; nothing imported.')
    return {'summary': dict(Counter(row['action'] for row in rows)), 'records': rows}, mapping, creates


def media_manifest(document, media_root):
    root = Path(media_root).resolve()
    references = []
    for row in document['records']:
        for key, field in fields_for(model_for(row['model'])).items():
            name = row['fields'][key]
            if isinstance(field, models.ImageField) and name:
                safe_key(name)
                path = (root / name).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('Image resolves outside MEDIA_ROOT.')
                entry = {'model': row['model'], 'pk': row['source_id'], 'field': key, 'key': name}
                if path.is_file():
                    try:
                        with Image.open(path) as picture:
                            picture.verify()
                        entry.update(status='valid_original', bytes=path.stat().st_size,
                                     sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                    except (OSError, ValueError):
                        entry['status'] = 'invalid_original'
                else:
                    entry['status'] = 'missing_original'
                references.append(entry)
    return {'images': references}


@transaction.atomic
def apply_catalog(document, backup_path, expected_plan=None):
    """Insert missing catalog rows only. Never patch or delete existing records."""
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [728410935102])
    plan, mapping, creates = plan_catalog(document)
    if expected_plan is not None and expected_plan != plan:
        raise ValueError('Target catalog changed since the reviewed preview; run a new dry-run.')
    backup = export_catalog()
    path = Path(backup_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(backup, handle, cls=DjangoJSONEncoder, indent=2)
    if json.loads(path.read_text(encoding='utf-8')) != backup:
        raise ValueError('Affected-catalog backup verification failed.')
    for row in creates:
        model = model_for(row['model'])
        data = {}
        for key, field in fields_for(model).items():
            value = row['fields'][key]
            if field.is_relation and value is not None:
                value = mapping[f'{field.related_model.__name__}:{value}']
                if value is None:
                    raise ValueError('Unresolved dependency during import.')
            data[field.attname] = value
        if row['model'] == 'Banner':
            data['link'], pending = remap_link(data['link'], mapping)
            if pending:
                raise ValueError('Unresolved banner destination.')
        obj = model(**data)
        obj.full_clean()
        obj.save(force_insert=True)
        mapping[ref(row)] = obj.pk
    return plan

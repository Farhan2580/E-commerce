import json
import sqlite3
from collections import Counter
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from shop.catalog_transfer import export_catalog, media_manifest, model_for, fields_for, plain, ref, IDENTITY


class Command(BaseCommand):
    help = 'Export allowlisted catalog records and audit media only. Never exports users/orders/payments.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)
        parser.add_argument('--baseline-sqlite', help='Historical LOCAL comparison only; never assumed to be production.')

    def handle(self, *args, **options):
        output = Path(options['output'])
        if output.exists():
            raise CommandError('Choose a new output directory; existing artifacts are never overwritten.')
        document = export_catalog()
        diff = {'comparison': 'No production comparison available.', 'records': []}
        if options['baseline_sqlite']:
            path = Path(options['baseline_sqlite']).resolve()
            if not path.is_file():
                raise CommandError('Historical local comparison file is missing.')
            source = sqlite3.connect('file:' + path.as_posix() + '?mode=ro', uri=True)
            source.row_factory = sqlite3.Row
            try:
                for row in document['records']:
                    model = model_for(row['model'])
                    table = model._meta.db_table
                    columns = {info[1] for info in source.execute(f'PRAGMA table_info("{table}")')}
                    old = source.execute(f'SELECT * FROM "{table}" WHERE id=?', [row['source_id']]).fetchone() if columns else None
                    changed, before = {}, {}
                    if old:
                        for key, field in fields_for(model).items():
                            if field.column not in columns:
                                value = field.get_default()
                            else:
                                value = old[field.column]
                                if field.get_internal_type() == 'JSONField' and isinstance(value, str):
                                    value = json.loads(value)
                                else:
                                    value = field.to_python(value)
                            before[key] = plain(value)
                            if before[key] != row['fields'][key]:
                                changed[key] = {'before': before[key], 'after': row['fields'][key]}
                    action = 'new_local' if not old else ('changed_local' if changed else 'unchanged_local')
                    row['identity_changed_locally'] = bool(old and any(key in changed for key in IDENTITY[row['model']]))
                    diff['records'].append({'ref': ref(row), 'model': row['model'], 'action': action,
                        'label': row['fields'].get('name', row['fields'].get('title', row['fields'].get('image', ''))), 'changes': changed})
            finally:
                source.close()
            diff['comparison'] = 'Current local catalog versus historical committed LOCAL SQLite, NOT production.'
        manifest = media_manifest(document, settings.MEDIA_ROOT)
        output.mkdir(parents=True)
        for name, value in [('catalog.json', document), ('local-diff.json', diff), ('media-manifest.json', manifest)]:
            (output / name).write_text(json.dumps(value, cls=DjangoJSONEncoder, indent=2), encoding='utf-8')
        summary = {'catalog_counts': dict(Counter(r['model'] for r in document['records'])),
                   'local_diff_counts': dict(Counter(r['action'] for r in diff['records'])),
                   'unique_image_keys': len({r['key'] for r in manifest['images']}),
                   'media_statuses': dict(Counter(r['status'] for r in manifest['images'])),
                   'production_compared': False, 'production_modified': False}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        self.stdout.write(json.dumps(summary, indent=2))
        self.stdout.write('Catalog artifacts saved. No database records or uploaded files changed.')

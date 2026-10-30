import hashlib
import json
import os
from pathlib import Path
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from PIL import Image
from shop.catalog_transfer import plan_catalog, apply_catalog, fields_for, model_for
from django.db.models import ImageField


class Command(BaseCommand):
    help = 'Dry-run catalog reconciliation. --apply inserts missing records only; existing catalog rows are never changed.'

    def add_arguments(self, parser):
        parser.add_argument('bundle')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--backup', help='New secure target-side affected-catalog backup file.')
        parser.add_argument('--expected-plan', help='SHA256 from the reviewed dry-run on this same target.')
        parser.add_argument('--media-manifest')
        parser.add_argument('--production-backup-verified', action='store_true')

    def handle(self, *args, **options):
        try:
            raw = Path(options['bundle']).read_bytes()
            document = json.loads(raw.decode('utf-8-sig'))
            if any(row.get('identity_changed_locally') for row in document.get('records', [])):
                raise ValueError('Local identity changes require manual reconciliation before additive import.')
            plan, _, creates = plan_catalog(document)
            digest = hashlib.sha256(raw + json.dumps(plan, sort_keys=True).encode()).hexdigest()
            self.stdout.write(json.dumps({**plan, 'plan_sha256': digest, 'applied': False}, indent=2))
            if not options['apply']:
                return
            if not options['backup'] or options['expected_plan'] != digest:
                raise ValueError('Apply requires a new backup path and the exact reviewed target plan hash.')
            if not options['production_backup_verified']:
                raise ValueError('Verify and retain production database/media backups before applying; then supply --production-backup-verified.')
            if os.environ.get('RENDER') == 'true' and settings.MEDIA_STORAGE not in {'cloudinary', 's3'}:
                raise ValueError('Production import requires persistent image storage.')
            keys = {row['fields'][key] for row in creates for key, field in fields_for(model_for(row['model'])).items()
                    if isinstance(field, ImageField) and row['fields'][key]}
            if keys:
                if not options['media_manifest']:
                    raise ValueError('A source image manifest is required to verify uploaded originals.')
                entries = json.loads(Path(options['media_manifest']).read_text(encoding='utf-8-sig'))['images']
                hashes = {entry['key']: entry.get('sha256') for entry in entries}
                for key in keys:
                    with default_storage.open(key, 'rb') as file:
                        actual = hashlib.file_digest(file, 'sha256').hexdigest()
                        file.seek(0)
                        Image.open(file).verify()
                    if actual != hashes.get(key):
                        raise ValueError('A required persistent image does not match the source original.')
            result = apply_catalog(document, options['backup'], expected_plan=plan)
            self.stdout.write(json.dumps({'applied': True, 'summary': result['summary'],
                                         'existing_records_updated': 0, 'records_deleted': 0}))
        except Exception as exc:
            # Provider/network exceptions may contain signed URLs or credentials.
            raise CommandError('Catalog transfer stopped safely: ' + type(exc).__name__ +
                               '. Review schema, ambiguity, backups, plan hash and persistent media.') from None

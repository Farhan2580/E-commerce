"""Scoped support link transfer; dry-run by default, never updates existing links."""
import hashlib
import json
import os
from pathlib import Path

from django.core.files.storage import default_storage
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from PIL import Image

from shop.catalog_transfer import safe_key
from shop.models import BusinessLink
from shop.whatsapp import whatsapp_url

FIELDS = ('label_en', 'label_bn', 'url', 'image', 'is_verified', 'position')


def snapshot():
    return list(BusinessLink.objects.filter(kind='whatsapp').order_by('pk').values('pk', *FIELDS, 'updated_at'))


class Command(BaseCommand):
    help = 'Export one WhatsApp BusinessLink, or preview an insert-only transfer with media verification.'

    def add_arguments(self, parser):
        parser.add_argument('bundle', nargs='?')
        parser.add_argument('--export', dest='export_path')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--expected-plan')
        parser.add_argument('--backup')
        parser.add_argument('--production-backup-verified', action='store_true')

    def handle(self, *args, **options):
        try:
            if options['export_path']:
                rows = snapshot()
                if len(rows) != 1 or options['apply'] or options['bundle']:
                    raise ValueError('Export requires exactly one configured WhatsApp link.')
                fields = {key: rows[0][key] for key in FIELDS}
                document = {'format': 'gadgetflow-whatsapp-v1', 'fields': fields, 'images': []}
                if fields['image']:
                    with default_storage.open(fields['image'], 'rb') as body:
                        digest = hashlib.file_digest(body, 'sha256').hexdigest()
                        body.seek(0)
                        Image.open(body).verify()
                    document['images'].append({'key': fields['image'], 'sha256': digest})
                with Path(options['export_path']).open('x', encoding='utf-8') as output:
                    json.dump(document, output, indent=2)
                self.stdout.write('WhatsApp-only bundle exported; no database changes.')
                return
            document = json.loads(Path(options['bundle']).read_text(encoding='utf-8-sig'))
            fields = document['fields']
            if document['format'] != 'gadgetflow-whatsapp-v1' or set(fields) != set(FIELDS):
                raise ValueError('Invalid widget bundle.')
            safe_key(fields['image'])
            if not whatsapp_url(fields['url']):
                raise ValueError('Explicit international WhatsApp destination required.')
            candidate = BusinessLink(kind='whatsapp', **fields)
            candidate.full_clean()
            with transaction.atomic():
                if connection.vendor == 'postgresql':
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [728019234])
                before = snapshot()
                action = 'create' if not before else 'identical' if len(before) == 1 and all(
                    before[0][key] == fields[key] for key in FIELDS) else 'preserve_existing'
                plan = {'action': action, 'source': document, 'target': before}
                digest = hashlib.sha256(json.dumps(plan, sort_keys=True, default=str).encode()).hexdigest()
                self.stdout.write(json.dumps({**plan, 'plan_sha256': digest, 'applied': False}, default=str, indent=2))
                if not options['apply']:
                    return
                if action == 'preserve_existing':
                    raise ValueError('Production WhatsApp configuration differs; reconcile fields explicitly in Admin.')
                if not options['production_backup_verified'] or not options['backup'] or options['expected_plan'] != digest:
                    raise ValueError('Apply requires verified backups, a new backup file and the reviewed target plan hash.')
                if os.environ.get('RENDER') == 'true' and settings.MEDIA_STORAGE not in {'cloudinary', 's3'}:
                    raise ValueError('Production transfer requires persistent media storage.')
                if fields['image']:
                    hashes = {row['key']: row['sha256'] for row in document['images']}
                    with default_storage.open(fields['image'], 'rb') as body:
                        actual = hashlib.file_digest(body, 'sha256').hexdigest()
                        body.seek(0)
                        Image.open(body).verify()
                    if actual != hashes.get(fields['image']):
                        raise ValueError('Persistent portrait differs from source original.')
                with Path(options['backup']).open('x', encoding='utf-8') as backup:
                    json.dump({'format': 'gadgetflow-whatsapp-backup-v1', 'records': before}, backup, default=str, indent=2)
                if action == 'create':
                    candidate.save()
                self.stdout.write(json.dumps({'applied': True, 'created': int(action == 'create'), 'updated': 0}))
        except Exception as exc:
            # Provider errors can contain signed URLs; do not echo exceptions.
            raise CommandError('WhatsApp transfer stopped safely: ' + type(exc).__name__ +
                               '. Check bundle, conflicts, plan, backups and portrait storage.') from None

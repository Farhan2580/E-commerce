"""Audit originals and optionally copy exact keys to S3 without changing records."""
import hashlib
import json
import mimetypes
from pathlib import Path, PurePosixPath

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ImageField
from PIL import Image


class Command(BaseCommand):
    help = 'Audit every image reference; --upload copies originals to S3/Cloudinary without overwriting or changing DB references.'

    def add_arguments(self, parser):
        parser.add_argument('--source', default=str(settings.MEDIA_ROOT))
        parser.add_argument('--upload', action='store_true')
        parser.add_argument('--manifest', help='Read references from an inspect_media JSON report instead of querying the database.')

    def handle(self, *args, **options):
        source = Path(options['source']).resolve()
        if not source.is_dir():
            raise CommandError('Source directory does not exist.')
        upload = options['upload']
        if upload and settings.MEDIA_STORAGE not in {'s3', 'cloudinary'}:
            raise CommandError('--upload requires MEDIA_STORAGE=s3 or cloudinary; no filesystem writes are performed.')
        records = []
        names = {}
        if options['manifest']:
            try:
                document = json.loads(Path(options['manifest']).read_text(encoding='utf-8-sig'))
                entries = document.get('images', document.get('references'))
                if not isinstance(entries, list) or not entries:
                    raise ValueError
                for entry in entries:
                    name = entry.get('key', entry.get('name'))
                    if not isinstance(name, str) or not name:
                        raise ValueError
                    # Recovery manifests deliberately contain no database IDs,
                    # model names, record contents, or internal storage paths.
                    records.append({'model': entry.get('model', 'ImageField'), 'pk': entry.get('pk'),
                                    'field': entry.get('field', 'image'), 'name': name})
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                raise CommandError('Manifest must be a nonempty inspect_media/transfer_media JSON report.')
        else:
            for model in apps.get_app_config('shop').get_models():
                for field in model._meta.fields:
                    if isinstance(field, ImageField):
                        for pk, name in model.objects.exclude(**{field.name: ''}).exclude(**{field.name: None}).values_list('pk', field.name):
                            records.append({'model': model.__name__, 'pk': pk, 'field': field.name, 'name': name})
        for row in records:
            if settings.MEDIA_STORAGE == 'cloudinary':
                row['public_id'] = default_storage.public_id(row['name'])
            names.setdefault(row['name'], []).append(row)
        failed = False
        for name, rows in names.items():
            path = (source / name).resolve()
            if not path.is_relative_to(source) or '\\' in name or PurePosixPath(name).is_absolute():
                raise CommandError('Unsafe image key: ' + name)
            status = 'missing_original'
            if path.is_file():
                try:
                    with Image.open(path) as image:
                        image.verify()
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    status = 'valid_original'
                    for row in rows:
                        row['sha256'] = digest
                    if upload and settings.MEDIA_STORAGE == 'cloudinary':
                        try:
                            with path.open('rb') as body:
                                status = default_storage.transfer_original(name, body, digest)
                        except Exception as exc:
                            # Do not print provider errors containing request details.
                            status = 'storage_error:' + type(exc).__name__
                    elif upload:
                        # Conditional PUT is atomic: even a concurrent uploader cannot
                        # overwrite an existing object or silently rename its key.
                        from botocore.exceptions import ClientError
                        key = '/'.join(filter(None, [default_storage.location, name]))
                        try:
                            with path.open('rb') as body:
                                default_storage.connection.meta.client.put_object(
                                    Bucket=default_storage.bucket_name, Key=key, Body=body,
                                    ContentType=mimetypes.guess_type(name)[0] or 'application/octet-stream',
                                    IfNoneMatch='*')
                            status = 'uploaded'
                        except ClientError as exc:
                            if exc.response['ResponseMetadata']['HTTPStatusCode'] != 412:
                                raise
                            with default_storage.open(name, 'rb') as existing:
                                matches = hashlib.file_digest(existing, 'sha256').hexdigest() == digest
                            status = 'existing_identical' if matches else 'conflict_not_overwritten'
                except (OSError, ValueError) as exc:
                    status = 'invalid_original:' + type(exc).__name__
            failed |= status not in {'valid_original', 'uploaded', 'existing_identical'}
            for row in rows:
                row['status'] = status
        self.stdout.write(json.dumps({'source': str(source), 'upload': upload, 'references': records}, indent=2))
        if failed:
            raise CommandError('Missing, invalid, or conflicting originals; see exact records above. Database unchanged.')

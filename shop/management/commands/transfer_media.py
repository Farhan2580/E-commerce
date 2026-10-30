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
    help = 'Audit every image reference against original files; --upload copies missing S3 keys without overwriting.'

    def add_arguments(self, parser):
        parser.add_argument('--source', default=str(settings.MEDIA_ROOT))
        parser.add_argument('--upload', action='store_true')

    def handle(self, *args, **options):
        source = Path(options['source']).resolve()
        if not source.is_dir():
            raise CommandError('Source directory does not exist.')
        upload = options['upload']
        if upload and settings.MEDIA_STORAGE != 's3':
            raise CommandError('--upload requires MEDIA_STORAGE=s3; no filesystem writes are performed.')
        records = []
        names = {}
        for model in apps.get_app_config('shop').get_models():
            for field in model._meta.fields:
                if isinstance(field, ImageField):
                    for pk, name in model.objects.exclude(**{field.name: ''}).exclude(**{field.name: None}).values_list('pk', field.name):
                        row = {'model': model.__name__, 'pk': pk, 'field': field.name, 'name': name}
                        records.append(row)
                        names.setdefault(name, []).append(row)
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
                    if upload:
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

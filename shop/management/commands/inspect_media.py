"""Read-only storage and HTTP diagnostics; never prints credentials/signatures."""
import json
from io import BytesIO
from urllib.parse import urlsplit, urlunsplit, urljoin
from urllib.request import urlopen
from urllib.error import HTTPError

from PIL import Image
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ImageField


class Command(BaseCommand):
    help = 'Trace database image keys, actual storage readability and optional HTTP responses.'

    def add_arguments(self, parser):
        parser.add_argument('--category-id', type=int)
        parser.add_argument('--http', action='store_true')
        parser.add_argument('--origin', help='Public origin for testing relative media URLs, e.g. https://your-app.onrender.com')
        parser.add_argument('--fail-on-error', action='store_true', help='Exit nonzero for missing/unreadable files, failed HTTP checks, or an empty selection.')

    def handle(self, *args, **options):
        rows = []
        for model in apps.get_app_config('shop').get_models():
            if options['category_id'] is not None and model.__name__ != 'Category':
                continue
            for field in model._meta.fields:
                if not isinstance(field, ImageField):
                    continue
                objects = model.objects.exclude(**{field.name: ''}).exclude(**{field.name: None})
                if options['category_id'] is not None:
                    objects = objects.filter(pk=options['category_id'])
                for obj in objects:
                    image = getattr(obj, field.name)
                    row = dict(model=model.__name__, pk=obj.pk, field=field.name, key=image.name,
                               backend=image.storage.__class__.__name__)
                    try:
                        url = image.url
                        parts = urlsplit(url)
                        row['url_without_signature'] = urlunsplit(parts._replace(query='', fragment=''))
                        row['signed_url'] = bool(parts.query)
                        try:
                            row['filesystem_path'] = image.path
                        except NotImplementedError:
                            row['bucket'] = getattr(image.storage, 'bucket_name', None)
                            row['object_key'] = '/'.join(filter(None, [getattr(image.storage, 'location', ''), image.name]))
                        row['exists'] = image.storage.exists(image.name)
                        with image.open('rb') as handle:
                            original = Image.open(handle)
                            row['format'] = original.format
                            original.verify()
                        row['readable_image'] = True
                    except Exception as exc:
                        row['storage_error'] = type(exc).__name__
                    if options['http'] and 'url_without_signature' in row:
                        if not parts.netloc and not options['origin']:
                            row['http_error'] = 'Relative URL: supply --origin to test production serving'
                        else:
                            try:
                                with urlopen(urljoin(options['origin'] or '', url), timeout=30) as response:
                                    row['http_status'] = response.status
                                    row['content_type'] = response.headers.get('Content-Type', '')
                                    Image.open(BytesIO(response.read(25 * 1024 * 1024))).verify()
                                    row['http_valid_image'] = response.status == 200 and row['content_type'].startswith('image/')
                            except HTTPError as exc:
                                row['http_status'] = exc.code
                                row['content_type'] = exc.headers.get('Content-Type', '')
                            except Exception as exc:
                                row['http_error'] = type(exc).__name__
                    rows.append(row)
        self.stdout.write(json.dumps({'configuration': {
            'debug': settings.DEBUG,
            'media_storage': settings.MEDIA_STORAGE,
            'media_root': str(settings.MEDIA_ROOT),
            'media_url': settings.MEDIA_URL,
            'backend': settings.STORAGES['default']['BACKEND'],
        }, 'images': rows}, indent=2))
        if options['fail_on_error'] and (not rows or any(
                not row.get('readable_image') or (options['http'] and not row.get('http_valid_image'))
                for row in rows)):
            raise CommandError('Media verification failed; inspect the JSON report above.')

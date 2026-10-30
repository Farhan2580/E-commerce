import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.files, deploy=True)
def production_media_storage(app_configs, **kwargs):
    if os.environ.get('RENDER') == 'true' and settings.MEDIA_STORAGE not in {'s3', 'cloudinary'}:
        return [Error(
            'Render uploads are using filesystem storage without production media serving.',
            hint='Configure MEDIA_STORAGE=s3 or cloudinary and the credentials from PRODUCTION_MEDIA.md; '
                 'transfer original media before deployment. collectstatic does not copy uploads.',
            id='shop.E001',
        )]
    return []


@register(Tags.database, deploy=True)
def production_database(app_configs, **kwargs):
    if os.environ.get('RENDER') == 'true' and settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
        return [Error(
            'Render is using repository-local SQLite instead of a persistent database.',
            hint='Back up the current production database before configuring persistent DATABASE_URL and DATABASE_USE_URL=1. '
                 'Do not replace production data with local db.sqlite3.', id='shop.E002',
        )]
    return []


@register(Tags.security, deploy=True)
def production_debug(app_configs, **kwargs):
    if os.environ.get('RENDER') == 'true' and settings.DEBUG:
        return [Error('DEBUG must be False on Render. Set DJANGO_DEBUG=0.', id='shop.E003')]
    return []

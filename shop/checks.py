import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.files, deploy=True)
def production_media_storage(app_configs, **kwargs):
    if os.environ.get('RENDER') == 'true' and settings.MEDIA_STORAGE != 's3':
        return [Error(
            'Render uploads are using filesystem storage without production media serving.',
            hint='Configure MEDIA_STORAGE=s3 and the bucket/credentials from PRODUCTION_MEDIA.md; '
                 'transfer original media before deployment. collectstatic does not copy uploads.',
            id='shop.E001',
        )]
    return []

"""Compatibility URLs for public catalog images moved to object storage."""
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.apps import apps
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import ImageField
from django.http import Http404, HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@require_safe
def media_redirect(request, name):
    if (settings.MEDIA_STORAGE != 's3' or '\\' in name
            or name.startswith('/') or '..' in PurePosixPath(name).parts):
        raise Http404
    # Only public catalog image references, never arbitrary bucket objects.
    known = any(
        model.objects.filter(**{field.name: name}).exists()
        for model in apps.get_app_config('shop').get_models()
        for field in model._meta.fields if isinstance(field, ImageField)
    )
    if not known:
        raise Http404
    url = default_storage.url(name)
    if urlsplit(url).scheme != 'https' or not urlsplit(url).netloc:
        raise Http404
    # Temporary, uncached redirect: private-bucket signatures expire.
    return HttpResponseRedirect(url)

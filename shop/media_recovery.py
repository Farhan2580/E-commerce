"""Temporary authenticated, read-only recovery of referenced image originals."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
from io import BytesIO
from pathlib import Path, PurePosixPath
import re

from PIL import Image
from django.apps import apps
from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.db.models import ImageField
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.debug import sensitive_variables


MAX_BYTES = 25 * 1024 * 1024
PAGE_SIZE = 10


def private_response(response):
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['Vary'] = 'Authorization'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
    return response


@sensitive_variables('token', 'provided')
def authorized(request):
    token = settings.MEDIA_RECOVERY_TOKEN
    if (not settings.MEDIA_RECOVERY_ENABLED or settings.DEBUG or not request.is_secure()
            or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', token)):
        return False
    try:
        expiry = datetime.fromisoformat(settings.MEDIA_RECOVERY_EXPIRES_AT.replace('Z', '+00:00'))
        remaining = expiry - datetime.now(timezone.utc)
        if not timedelta(0) < remaining <= timedelta(hours=24):
            return False
    except (ValueError, TypeError, OverflowError):
        return False
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if not header.startswith('Bearer ') or len(header) > 512:
        return False
    provided = header[7:]
    return hmac.compare_digest(provided.encode('utf-8'), token.encode('utf-8'))


def recovery_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not authorized(request):
            # No templates, redirects, cookies, or database queries on rejection.
            return private_response(HttpResponse(status=404))
        if request.method != 'GET':
            response = HttpResponse(status=405)
            response['Allow'] = 'GET'
            return private_response(response)
        try:
            response = view(request, *args, **kwargs)
        except Exception:
            # No exception strings, absolute paths, credentials or debug reports.
            response = JsonResponse({'error': 'recovery_unavailable'}, status=503)
        return private_response(response)
    return wrapped


def safe_key(key):
    return (isinstance(key, str) and 0 < len(key) <= 512
            and not PurePosixPath(key).is_absolute() and '\\' not in key and ':' not in key
            and all(part not in {'', '.', '..'} for part in key.split('/')))


def image_keys():
    keys = set()
    for model in apps.get_app_config('shop').get_models():
        for field in model._meta.fields:
            if isinstance(field, ImageField):
                keys.update(model.objects.exclude(**{field.name: ''}).exclude(
                    **{field.name: None}).values_list(field.name, flat=True))
    return sorted(keys)


def source_storage(request):
    source = request.GET.get('source', 'local')
    if source == 'local':
        return source, FileSystemStorage(location=settings.MEDIA_ROOT)
    if source == 'configured':
        return source, default_storage
    raise ValueError('invalid source')


def download_id(source, key):
    return hmac.new(settings.MEDIA_RECOVERY_TOKEN.encode('utf-8'),
                    (source + '\0' + key).encode('utf-8'), hashlib.sha256).hexdigest()


def read_original(storage, key):
    if not safe_key(key):
        return {'status': 'unsafe_key'}, None
    if isinstance(storage, FileSystemStorage):
        root = Path(storage.location).resolve()
        if not (root / key).resolve().is_relative_to(root):
            return {'status': 'unsafe_key'}, None
    try:
        if not storage.exists(key):
            return {'status': 'missing'}, None
        payload = BytesIO()
        size = 0
        with storage.open(key, 'rb') as original:
            for chunk in iter(lambda: original.read(1024 * 1024), b''):
                size += len(chunk)
                if size > MAX_BYTES:
                    return {'status': 'too_large'}, None
                payload.write(chunk)
        content = payload.getvalue()
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            image.verify()
        return {'status': 'ready', 'bytes': size, 'format': image_format,
                'sha256': hashlib.sha256(content).hexdigest()}, content
    except FileNotFoundError:
        return {'status': 'missing'}, None
    except Exception:
        return {'status': 'unreadable'}, None


@recovery_only
def manifest(request):
    try:
        offset = int(request.GET.get('offset', '0'))
        if offset < 0:
            raise ValueError
        source, storage = source_storage(request)
    except ValueError:
        return JsonResponse({'error': 'invalid_request'}, status=400)
    keys = image_keys()
    rows = []
    for key in keys[offset:offset + PAGE_SIZE]:
        diagnostics, _ = read_original(storage, key)
        row = {'key': key, **diagnostics}
        if diagnostics['status'] == 'ready':
            row['download_id'] = download_id(source, key)
        rows.append(row)
    next_offset = offset + PAGE_SIZE if offset + PAGE_SIZE < len(keys) else None
    return JsonResponse({'source': source, 'images': rows, 'next_offset': next_offset})


@recovery_only
def original(request, identifier):
    if not re.fullmatch(r'[a-f0-9]{64}', identifier):
        return HttpResponse(status=404)
    try:
        source, storage = source_storage(request)
    except ValueError:
        return JsonResponse({'error': 'invalid_request'}, status=400)
    key = next((key for key in image_keys() if safe_key(key) and
                hmac.compare_digest(download_id(source, key), identifier)), None)
    if key is None:
        return HttpResponse(status=404)
    diagnostics, payload = read_original(storage, key)
    if diagnostics['status'] != 'ready':
        return JsonResponse({'error': diagnostics['status']}, status=404)
    response = FileResponse(BytesIO(payload), as_attachment=True,
                            filename='original-image.bin', content_type='application/octet-stream')
    response['X-Media-SHA256'] = diagnostics['sha256']
    return response

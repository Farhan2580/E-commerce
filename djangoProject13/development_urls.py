"""Uploaded files are served only by an explicitly selected local configuration."""
from ipaddress import ip_address

from django.conf import settings
from django.http import Http404
from django.urls import re_path
from django.views.static import serve
from .urls import urlpatterns as application_patterns


def local_media(request, path):
    try:
        peer = ip_address(request.META.get('REMOTE_ADDR', ''))
        local = peer.is_loopback or bool(getattr(peer, 'ipv4_mapped', None) and peer.ipv4_mapped.is_loopback)
    except ValueError:
        local = False
    if not local:
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT, show_indexes=False)


urlpatterns = [re_path(r'^media/(?P<path>.*)$', local_media, name='local_media'), *application_patterns]

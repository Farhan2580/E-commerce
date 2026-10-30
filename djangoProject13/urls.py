from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from shop import media_recovery

urlpatterns = [
    path('internal/media-recovery/manifest/', media_recovery.manifest, name='media_recovery_manifest'),
    path('internal/media-recovery/original/<str:identifier>/', media_recovery.original, name='media_recovery_original'),
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # ✅ Add this line
]

if settings.MEDIA_STORAGE in {'s3', 'cloudinary'}:
    from shop.media_redirect import media_redirect
    urlpatterns += [path('media/<path:name>', media_redirect, name='stored_media')]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

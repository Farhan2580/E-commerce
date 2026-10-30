from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('shop.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # ✅ Add this line
]

if settings.MEDIA_STORAGE == 's3':
    from shop.media_redirect import media_redirect
    urlpatterns += [path('media/<path:name>', media_redirect, name='stored_media')]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

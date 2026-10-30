# Verified local media repair

For the separate live Render failure, durable object-storage setup and original
image transfer procedure, see [PRODUCTION_MEDIA.md](PRODUCTION_MEDIA.md).
The local success below does not mean production media is working.

The actual rendered homepage referenced:

`http://127.0.0.1:8000/media/products/gallery-7.jpg`

Before repair it returned **404, text/html; charset=utf-8**. This was not an image
or browser-blocking error: Product #1 (Royal Enfield), field `image`, stored
`products/gallery-7.jpg` through `FileSystemStorage`. Its physical file at
`media/products/gallery-7.jpg` existed and decoded as a valid JPEG.

All 15 nonempty database image fields pointed to valid physical images. None were
missing. All 14 distinct homepage media URLs failed because debug was off and
the base URL configuration's development-only `static()` helper omitted the media
route. The base URL configuration also contained a redundant second helper call.
Templates already used storage-backed `.image.url` values correctly.

## Implemented separation

- `manage.py`: normal `runserver` defaults to `djangoProject13.development`.
  Other management commands default to base settings; explicit environment or
  `--settings` selection is respected.
- `djangoProject13/development.py`: selects the local URL configuration and allows
  localhost/loopback hosts. It inherits existing storage and debug settings.
- `djangoProject13/development_urls.py`: serves `/media/` from the configured
  `MEDIA_ROOT` only to loopback peers. Directory indexes and parent traversal are
  unavailable. No public-host media fallback was added.
- `djangoProject13/urls.py`: removes a duplicate helper call; keeps the single
  normal DEBUG-only helper for explicit base debug development. Production with
  debug off has no Django media route. WSGI/ASGI still default to base settings.
- `.idea/djangoProject13.iml`: changes only the Django facet's local settings path;
  interpreter and other pre-existing edits are preserved.

Production upload serving must remain configured separately at the web server or
storage provider. WhiteNoise is for collected static assets, not user uploads.
No production service was deployed or modified by this repair.

## Verification

The stale local server was restarted. The exact original URL now returns
**200 image/jpeg**, and its response bytes decode as JPEG. Every distinct homepage
media URL was fetched and verified with Pillow; all **14/14** are valid images.
Database-backed JPEG, PNG, WebP and AVIF files were inspected without modification.
Existing category tiles intentionally use their first product's image where the
category has no uploaded image; existing product-linked banners use the linked
product's actual image where the banner has no upload. These fallback paths were
preserved, not replaced with placeholders.

`shop/test_media.py` uses an isolated Django test database and temporary media
directory. It uploads copies of two real existing project images to temporary
category, product and banner records, checks rendered URLs and valid HTTP image
bytes, then updates a product image through the actual Django Admin POST handler.
The test checks the new PNG URL and bytes, verifies the old file remains intact,
and checks the product detail page uses the new image. Other tests verify loopback
access, blocked parent paths/directories, and absent production upload routing.

No existing upload was replaced, renamed or deleted, and no existing model record
or template/design/payment code was changed for this repair.

Chrome checks passed at 1440px and 390px on the homepage, catalog, Product #1 detail
and offers pages: all targeted real images decoded, all 60 observed media requests
returned HTTP 200 with image MIME types, and no horizontal overflow or JavaScript
exceptions occurred. The complete 92-test suite passed, including four media tests.
Before/after audit records were identical for existing image references, and the
physical upload count stayed at 22. Django checks passed for base and development
settings. The corrected server was left running on `http://127.0.0.1:8000/`.

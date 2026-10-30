# Production media recovery on Render

Prepared locally; nothing pushed, deployed, or uploaded to remote storage.

## Observed failure (2026-10-30)

The live homepage at https://farhan-gadgetflow.onrender.com/ references
https://farhan-gadgetflow.onrender.com/media/products/gallery-7.jpg.
An actual GET returned **404**, `text/html; charset=utf-8`, not image bytes.
All 14 distinct homepage media URLs returned 404. A second read-only HTTP audit
covered `/`, `/products/`, and `/product/1/`; see the verification procedure below.

The matching LOCAL record is Product #1, Royal Enfield, `image` =
`products/gallery-7.jpg`. Its local original `media/products/gallery-7.jpg`
is a valid JPEG. All 15 nonempty local ImageField references have valid originals;
there are no missing originals among those references (22 files exist in media).
Category and product-linked hero banner fallbacks reuse product image fields;
they do not need new placeholder uploads. Templates already use storage-backed URLs.

Checked-in production settings previously selected `FileSystemStorage`,
`MEDIA_ROOT=BASE_DIR/media`, `MEDIA_URL=/media/`. WhiteNoise handles static assets,
while the production URL configuration deliberately has no upload route with
DEBUG off. A media file can therefore exist on Render and still return 404.
This is a confirmed serving/configuration mismatch, not proof files were lost.

No Render API/dashboard/SSH connection, production database, or storage credentials
were available. No AWS/MEDIA/CLOUDINARY/RENDER variable names were present in this
local process. Actual Render runtime environment variables, mount configuration,
and on-server file existence remain unverified. Local DB matching does not prove
production DB equality. Render's default filesystem is ephemeral, so missing files
could also have been lost on restart or never transferred; distinguish with the
production inventory before recovery. Do not expose secrets when collecting it.

## Integration

`MEDIA_STORAGE=s3` selects django-storages' S3 backend for uploads only.
WhiteNoise/static storage stays unchanged. No model changes, development routes,
DEBUG changes, payment changes, image renames, or database writes are involved.
New uploads use unique filenames instead of overwriting prior objects.

Works with AWS S3 and compatible providers such as R2. If Render already has a
provider, reuse its bucket/endpoint and existing object-key prefix. Do not change
providers or prefixes without inventorying existing keys first.

## Operator setup (not performed)

1. Back up the production database and any surviving uploads. In Render Shell,
   run `python manage.py shell` and inspect only these nonsecret values:
   `settings.DEBUG`, `settings.MEDIA_ROOT`, `settings.MEDIA_URL`,
   `settings.STORAGES['default']['BACKEND']`. Inspect environment variable NAMES
   and storage/mount details in the dashboard; never print access keys/passwords.
   Inspect `Product.objects.get(pk=1).image.name` and whether its storage reports
   `.exists(name)`. Export the production image-field inventory to compare names
   with local originals. Do not replace the production DB with the local SQLite DB.
2. Provision or reuse an S3-compatible bucket and credentials scoped to that bucket.
   Enable bucket versioning/backups where supported. The uploader needs List/Get/Put
   access for the media prefix. The provider must support conditional PutObject
   (`If-None-Match: *`); if it does not, do not bypass that safeguard.
3. Install `requirements.txt` locally and in the Render build. Configure the local
   transfer process using environment variables from `.env.example`:

   ```text
   MEDIA_STORAGE=s3
   AWS_STORAGE_BUCKET_NAME=<bucket>
   AWS_ACCESS_KEY_ID=<secret in environment>
   AWS_SECRET_ACCESS_KEY=<secret in environment>
   AWS_S3_REGION_NAME=<bucket region; auto for R2>
   AWS_S3_ENDPOINT_URL=<HTTPS S3-compatible API endpoint; empty for AWS S3>
   AWS_S3_ADDRESSING_STYLE=auto
   AWS_MEDIA_LOCATION=media
   AWS_QUERYSTRING_AUTH=1
   AWS_S3_CUSTOM_DOMAIN=
   DJANGO_DEBUG=0
   ```

   The project does NOT automatically load `.env`. Export variables into the process
   or set them in Render's Environment panel. Do not commit credentials.
   Private buckets use signed image URLs by default. For public media behind a CDN,
   configure a read-only public origin/CDN, set `AWS_S3_CUSTOM_DOMAIN` to its hostname
   (no scheme/path), and `AWS_QUERYSTRING_AUTH=0`. Unsigned custom-domain URLs require
   actual public read access. Never make a mixed private/customer-document bucket public.
   Restrict bucket/CDN content to uploaded media and preserve MIME types.
4. Audit local originals first:

   ```sh
   python manage.py transfer_media --source /absolute/path/to/original/media
   ```

   It prints model, primary key, field, key, SHA-256 and validity. Compare to the
   PRODUCTION inventory, including uploads made after this local database snapshot.
   Missing keys are reported precisely; restore them from backups or obtain the
   original files. No substituted or generated images are used.
5. With authorized storage access, transfer originals once:

   ```sh
   python manage.py transfer_media --source /absolute/path/to/original/media --upload
   ```

   A record key `products/gallery-7.jpg` becomes object key
   `media/products/gallery-7.jpg` with the default prefix. Existing identical files
   are skipped. Conflicting bytes are reported and never replaced; the command exits
   nonzero. Conditional writes prevent overwrite races and silent key renaming.
   The command never updates DB fields. Preserve the seven unreferenced local files
   in the backup too; this command transfers referenced originals, not arbitrary files.
6. After successful transfer and key comparison, set the same storage configuration
   on Render and deploy the prepared code when approved. Retain the current start
   command/production database. Normal `collectstatic --noinput` remains a static
   build step, not a media migration. Do not enable DEBUG or add Django media routes.
7. Verify rendered banner, category tile, catalog card and detail image URLs now use
   the bucket/CDN (signed URLs if private) and return 200 image bytes. The old app
   `/media/...` URLs redirect (302, uncached) to HTTPS object storage when S3 mode
   is enabled and the name matches an existing catalog ImageField. Following the
   redirect must return HTTP 200 with valid image bytes. Freshly rendered
   `.image.url` values point directly at object storage. No local files are served
   by this compatibility route; unknown bucket keys remain inaccessible through it.
   Test a new Admin upload, restart/redeploy, then verify both old and new images.

## Verification

```sh
python manage.py check
python manage.py test shop --noinput
python tools/verify_media_http.py http://127.0.0.1:8000
python tools/verify_media_http.py https://farhan-gadgetflow.onrender.com
```

The HTTP tool fetches every img URL rendered by home/catalog/Product #1 detail,
plus the three exact originally failing `/media/...` URLs. It follows redirects,
requires final status 200 and an image Content-Type, and decodes bytes with Pillow.
It exits nonzero for broken images. A redirect alone is not a successful check.
For a different production product ID, adjust the detail path in the tool.
Local existing media tests additionally exercise real category, hero, card and
product detail uploads through storage and HTTP; production tests confirm no
Django upload-serving route exists. Transfer tests cover missing originals,
exact object keys and non-overwriting conflict behavior with mocked S3 responses.
They do not prove connectivity to an unconfigured bucket.

## Alternative: persistent disk

If object storage is unavailable, use a paid Render persistent disk mounted at
`/var/data`, a filesystem upload root beneath it, and a production web server
(such as nginx) serving only that uploads directory. That alternative still needs
web-server/storage configuration and original-file transfer; it is not implemented
by selecting filesystem mode here. Render's disk alone does not serve HTTP files.
Keep database persistence separate; the current checked-in SQLite setting also
requires its own durable production arrangement. No database configuration was
changed as part of this media repair.

References:
- https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
- https://render.com/docs/disks

### Results from this preparation

- `manage.py check`: passed; also passed with isolated S3 configuration and dummy
  credentials (URL construction only, no remote storage access).
- Full suite: 107 tests passed.
- Actual local HTTP audit: 14/14 unique image URLs returned valid image bytes.
- Actual live HTTP audit: 0/14 unique image URLs valid; all returned 404. Home,
  catalog and Product #1 detail rendered 14, 11 and 2 image references respectively.
- S3 URLs preserve `/media/products/gallery-7.jpg` with the default prefix;
  signatures are enabled and overwrite is disabled.
- No remote upload, push or deployment was performed. No production credentials,
  mount inspection, or remote file listing was available. Live recovery remains
  pending storage setup, production inventory comparison, transfer and deployment.

### Exact-path trace

| Existing URL path | Local database field | Valid local original | Object key with default prefix |
| --- | --- | --- | --- |
| `/media/products/gallery-7.jpg` | Product #1 `image` | `media/products/gallery-7.jpg` (JPEG) | `media/products/gallery-7.jpg` |
| `/media/product_images/asus.webp` | Product #3 `image` | `media/product_images/asus.webp` (WebP) | `media/product_images/asus.webp` |
| `/media/offers/Macbook-Offer-Banner-5750.jpg` | Offer #4 `image` | `media/offers/Macbook-Offer-Banner-5750.jpg` (JPEG) | `media/offers/Macbook-Offer-Banner-5750.jpg` |

These mappings were re-audited without uploads or database writes. None of these
originals is missing. Production paths and object availability must still be checked
against the production database; no Render shell or provider credentials are available.
The local configuration proves production filesystem media would not be served with
DEBUG off, but public 404 responses alone cannot distinguish absent remote files
from an absent media handler. Do not describe file loss or a failed transfer as proven.

After the operator completes setup, transfer and deployment, rerun:

```sh
python tools/verify_media_http.py https://farhan-gadgetflow.onrender.com
```

The `exact_legacy_paths` group must pass for all three URLs, in addition to the
rendered image checks. Compatibility requests first return a temporary redirect;
final storage responses must be HTTP 200, image MIME types, and decodable originals.
Direct HTTP 200 responses on the app host without redirects would require an edge
proxy instead; this repair intentionally serves image bytes from durable storage.

Follow-up verification: 109 tests passed, including HTTPS storage redirect,
no local file serving, cache prevention for signed redirects, and rejection of
unknown/unsafe keys. Django checks pass with S3 settings; all three exact URL
paths resolve to the storage compatibility handler in that mode. A fresh live
GET of each of the three exact URLs still returned 404 `text/html; charset=utf-8`.
No upload/deployment was performed; production recovery is still pending.

## New category uploads: production diagnosis and release gate

`Category.image` uses `upload_to='categories/'`. Category Admin saves that ImageField
through default storage; the homepage renders `category.image.url`, not a hardcoded
static path. The same default storage handles Product, Banner and Offer images.
No template rewrite or collectstatic step can make a local upload durable on Render.

The public HTML inspected during this follow-up contained no `/media/categories/`
image URL. The local database also had no nonempty Category.image reference.
Therefore the customer's newly uploaded production category could not be identified
from public HTML or the local snapshot. Its exact production PK, filename, existence
and restart persistence cannot honestly be asserted without production diagnostics.

After making the prepared code available to an operator, use Render Shell:

```sh
python manage.py inspect_media --category-id ACTUAL_CATEGORY_ID --http
# Or inspect all product/category/banner/offer/gallery/logo fields:
python manage.py inspect_media --http
```

This is read-only: it reports the DB key, backend, filesystem path or bucket object
key, storage existence, actual decoded file readability, URL (without signatures),
and optional final HTTP status/image validation. It prints no credentials.
An empty image list means the selected category has no saved image or does not exist.
For the current filesystem configuration, `--http` reports a relative URL; test that
path against the live host separately and compare its response to local readability.

Interpretation:
- Readable filesystem file + live 404: upload saved, but production media is unserved.
- Filesystem file absent: missing file; use Render logs/backups to distinguish never
  transferred from lost on restart. A 404 alone cannot distinguish these histories.
- S3 exists/readable + HTTP 403: inspect signed-URL settings, CDN/public access policy.
- Wrong DB key: compare original file and exact key; do not rewrite all records.
- HTTP 500: inspect Render logs and storage credentials/backend errors.

The new deploy-only `shop.E001` check rejects Render filesystem mode. Add this to
the Render build/predeployment checks after installing requirements:

```sh
python manage.py check --deploy --tag files
```

Set `MEDIA_STORAGE=s3` explicitly in Render and configure the bucket, scoped
Get/Put/List credentials, region, endpoint (if compatible provider), prefix and
private signed URLs as described above. `.env.example` is documentation only;
Render must receive actual environment variables. This integration is already
prepared locally; it has not been activated on the live service.

Before switching, recover any category uploads still in the existing Render
MEDIA_ROOT and back them up with exact relative names. Compare the production
DB inventory against local originals, then run `transfer_media --source ... --upload`
with storage access. Local originals do not include any production-only new category
uploads. Never replace those with product images or placeholders.

After deployment, upload a category image in Admin, record its `inspect_media`
output and rendered homepage src, confirm final HTTP 200/image bytes, restart or
redeploy the service, and repeat the same checks. This persistence verification
requires operator access and was not performed here. S3 stores media independently
of the Render instance. A new local FileSystemStorage object can verify local
persistence but cannot demonstrate Render persistence.

### Comparing the local configuration to Render

Local `runserver` selects `djangoProject13.development`, whose URL configuration
serves `/media/` only to loopback clients. WSGI on Render selects base settings;
with filesystem storage and DEBUG off it has no such file-serving route. Thus
identical saved database paths can work in PyCharm and fail in production without
any template or Admin upload defect. The deployment's actual environment still
must be inspected to confirm which backend is running.

The diagnostic can now test relative media URLs against the live host while reading
the production file, and prints only nonsecret configuration values:

```sh
python manage.py inspect_media --category-id CATEGORY_ID --http --origin https://farhan-gadgetflow.onrender.com
```

Run this IN Render Shell against the live DB, not locally against the local DB.
The command does not need storage write access. Preserve its output, repeat after
restart, and compare file readability and HTTP results. Local execution cannot
confirm production file existence.

If this command has not been deployed yet, the operator can inspect the existing
code in Render Shell without deploying using `python manage.py shell`, then:

```python
from django.conf import settings
from shop.models import Category
print(settings.DEBUG, settings.MEDIA_ROOT, settings.MEDIA_URL)
print(settings.STORAGES['default']['BACKEND'])
print(list(Category.objects.exclude(image='').values('id', 'name', 'image')))
c = Category.objects.get(pk=CATEGORY_ID)
print(c.image.name, c.image.storage.__class__.__name__)
print('exists:', c.image.storage.exists(c.image.name))
from PIL import Image
with c.image.open('rb') as original:
    Image.open(original).verify()
from urllib.parse import urlsplit, urlunsplit
parts = urlsplit(c.image.url)
print(urlunsplit(parts._replace(query='', fragment='')))
```

Do not share credentials or signed URL query strings. After copying the actual
image URL privately from Admin, inspect it with an HTTP client and validate image
bytes. Also check the homepage category HTML uses this key. Featured/root category
visibility is separate from file storage; a category not selected for display will
not appear merely because it has an image.

## Release verification (strict exit statuses)

The existing S3 code only activates when Render's actual process environment sets
`MEDIA_STORAGE=s3`; pushing this repository does not supply credentials or transfer
media. No image recovery is complete until the production bucket and original
objects have been verified. Keep `DJANGO_DEBUG=0`.

Use these checks as release gates after configuring persistent storage:

```sh
python manage.py check --deploy --tag files
python manage.py inspect_media --http --fail-on-error --origin https://farhan-gadgetflow.onrender.com
python tools/verify_media_http.py https://farhan-gadgetflow.onrender.com --extra-url /media/categories/ACTUAL_NEW_UPLOAD_NAME.png
```

`--fail-on-error` makes missing/unreadable originals, failed image HTTP checks and
empty category selections fail the command. The HTTP tool now checks the offers
page too and accepts repeatable `--extra-url` arguments for actual new Admin uploads.
Do not use the example upload filename literally. Repeat these checks with the
SAME category key after redeployment to prove persistence. Preserve reports outside
version control, including timestamps and deployment commit IDs. A valid local
upload or successful GitHub push does not prove a Render rollout or durable storage.

The commit for this release must exclude local database, .env files, credentials,
and unrelated uploaded files. Store secrets directly in Render/storage settings.
GitHub commit/check status is not a Render deployment status unless the Render
integration explicitly reports it. When dashboard/API access is unavailable,
report the deployment as unverified and the live HTTP results as observed.

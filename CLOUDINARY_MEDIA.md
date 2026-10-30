# Optional Cloudinary media storage

Implemented locally; no Cloudinary upload, production data change, commit, push or
deployment was performed as part of this integration. Live connectivity and
persistence still require credentials and verification on the actual service.

## What changes, and what stays intact

- `MEDIA_STORAGE=filesystem` remains the default and retains existing local behavior.
- Existing S3 mode remains supported. `MEDIA_STORAGE=cloudinary` selects the new
  `shop.cloudinary_storage.CloudinaryMediaStorage` through Django 6 `STORAGES`.
- Product, Category, Banner, Offer, gallery, logo, preorder and other shop ImageField
  values keep their exact existing strings. No CloudinaryField conversion, schema
  migration, database replacement, or production record updates are required.
- Templates already use `image.url`. WhiteNoise and collectstatic remain exclusively
  for static application assets; media is delivered by Cloudinary over HTTPS.
- Legacy `/media/<key>` routes redirect known catalog keys to their storage URLs
  in Cloudinary mode. Following redirects must return a real HTTP 200 image.
- The backend intentionally does not implement asset deletion. Clearing/changing an
  image field does not remove the preserved original through this storage adapter.

## Exact Render environment variables

Set these on the EXISTING Render web service. Supply credentials securely, never in
Git, screenshots, logs, or chat. These same variables must reach the PyCharm terminal
process used for transfer; setting a PyCharm Run Configuration alone does not set
the environment of an already-open terminal. `.env` is not automatically loaded.

| Variable name | Value/purpose |
| --- | --- |
| `DJANGO_DEBUG` | `0` |
| `MEDIA_STORAGE` | `cloudinary` |
| `CLOUDINARY_CLOUD_NAME` | Your Cloudinary product environment cloud name |
| `CLOUDINARY_API_KEY` | Credential from that product environment |
| `CLOUDINARY_API_SECRET` | Secret credential from the same environment |
| `CLOUDINARY_MEDIA_PREFIX` | Optional; default `gadgetflow/media` |

All three credential variables must be supplied when this backend is selected.
This adapter uses the individual variables, not `CLOUDINARY_URL`. No unsigned upload
preset is needed. AWS variables are not used in Cloudinary mode. Keep current
database, secret-key, host and payment configuration unchanged for this media task.
Do not switch database backends or enable live payments to configure media.

Use a dedicated prefix and preserve its exact value across uploads and redeploys.
Prefix components may contain letters, numbers, underscores and hyphens, separated
by slashes; components such as `v123` are rejected. Maximum prefix length: 150.
The assets are public storefront images; do not use this backend for private files.
Disable incoming transformations/default upload settings that change originals;
the transfer verifies original bytes and fails rather than accepting altered bytes.

## Stable mapping, without rewriting DB values

Cloudinary image public IDs do not include file extensions. Dropping extensions
from legacy database paths could cause `photo.jpg` and `photo.png` to collide.
The adapter instead uses this deterministic ID:

```text
<CLOUDINARY_MEDIA_PREFIX>/<SHA-256 of the exact UTF-8 ImageField filename>
```

For example, `products/gallery-7.jpg` remains exactly that string in the database;
its Cloudinary public ID is `gadgetflow/media/` followed by the hash of that string.
The dry-run report prints the exact ID alongside each model/PK/field/key/hash.
The upload context records the original `django_path` and source byte digest.
Product/category/banner filenames therefore cannot alias by removing extensions.

URLs are reconstructed from the cloud name, prefix and key without a local manifest
or an API call per rendered image. A redeployed instance generates the same URL.
Do not rename assets/public IDs in Cloudinary or change cloud/prefix after migration.
Cloudinary Media Library folders may differ from public ID folders under dynamic
folder mode; the public ID in the report is the authoritative lookup key.

## Safe rollout and migration, step by step

On Render Free without Shell/SSH, use [MEDIA_RECOVERY_FREE.md](MEDIA_RECOVERY_FREE.md)
instead of the Shell export command below. Its authenticated export produces a
minimal compatible manifest without database IDs; the rollout loss warning applies.

1. Before changing Render environment variables (which may restart the service),
   back up the actual production database and recover surviving production uploads.
   Never substitute the local SQLite database. Keep local media backed up too.

2. Install requirements in PyCharm's terminal from the project root:

   ```powershell
   $py = '.\.venv\Scripts\python.exe'
   & $py -m pip install -r requirements.txt
   & $py manage.py check
   ```

   `cloudinary>=1.44,<2` is now in requirements. No django-cloudinary-storage package
   or model migration is needed. Local filesystem mode still works without credentials.

3. Export a read-only image-reference manifest from Render Shell, while it still
   uses its CURRENT production database/storage:

   ```sh
   python manage.py inspect_media > /tmp/production-media-manifest.json
   ```

   Download that JSON to `.local-backups/production-media-manifest.json` locally.
   The updated transfer command must be available locally. The JSON contains keys
   and diagnostics, not database contents or credentials. Exporting it does not
   update records. A storage error in a row does not erase the row's key.

   Obtain the exact original file for every referenced key. Production-only category
   uploads may be absent from the local directory: recover them from current storage
   or backups with their exact relative filenames. Do not invent replacements.

4. Configure Cloudinary variables in the LOCAL transfer process first, using the
   same cloud/prefix intended for Render. Leave database settings unchanged. Run:

   ```powershell
   & $py manage.py transfer_media --source '.\media' --manifest '.\.local-backups\production-media-manifest.json'
   ```

   This dry run makes no uploads and no DB queries/writes when using the manifest.
   It validates images, computes hashes, and shows each deterministic public ID.
   Resolve every missing/invalid original first. Without `--manifest`, the command
   audits references in the LOCAL database, not production: it may omit production-only
   categories and does not copy arbitrary unreferenced files from a directory.

5. After reviewing the dry run, transfer the exact same selection:

   ```powershell
   & $py manage.py transfer_media --source '.\media' --manifest '.\.local-backups\production-media-manifest.json' --upload
   ```

   Every Cloudinary upload specifies `overwrite=False`. The command never renames
   migration keys, deletes assets, or changes any DB field. It downloads the delivered
   original and compares its SHA-256 with the source. Outcomes:

   - `uploaded`: copied and byte-verified.
   - `existing_identical`: existing bytes match; no replacement.
   - `conflict_not_overwritten`: existing bytes differ; left intact, command fails.
   - `uploaded_bytes_mismatch`: new delivery differs; preserved, reported as failure.
   - `missing_original`, `invalid_original:*`, or `storage_error:*`: failure; investigate.

   The operation can partially upload before encountering a later failure. Re-running
   is safe: verified identical assets are skipped. Never force overwrites to resolve
   conflicts. Review conflicting keys and choose a separate reviewed prefix if needed.
   New Admin uploads use Django's alternate filename handling and cannot overwrite
   an existing asset, including a concurrent upload collision.

6. Only after transfer and checks, deploy the prepared code manually and activate
   the SAME Cloudinary configuration on Render. Preserve the existing production
   database. Do not reset, seed, import SQLite, or run a media DB migration. The existing
   Render build installs requirements; collectstatic does not migrate uploads.

7. Run in Render Shell:

   ```sh
   python manage.py check --deploy --tag files
   python manage.py inspect_media --http --fail-on-error
   ```

   From PyCharm, check the rendered site and original legacy URLs:

   ```powershell
   & $py tools/verify_media_http.py https://farhan-gadgetflow.onrender.com
   ```

   Require HTTP 200, an image Content-Type and decodable original bytes. Test category,
   product cards/detail, uploaded banners, product-linked hero banners and offers.
   Test one actual new Admin category upload, note its key/URL, redeploy, then repeat
   the SAME URL/readability check to verify persistence. Local mocked tests demonstrate
   stable mapping and safety, not live Cloudinary access or Render persistence.

## Rollback

Keep the original media backup and previous provider intact. Select the previous
MEDIA_STORAGE configuration and deploy manually if needed; no DB filename rollback
is required because the migration never modifies those strings. Files newly uploaded
only to Cloudinary need a separate exact-name copy to the previous storage before
such a rollback; otherwise those new image URLs will be unavailable there.

Official SDK/API references:
- https://cloudinary.com/documentation/django_integration
- https://cloudinary.com/documentation/image_upload_api_reference#upload

Local validation: all 126 shop tests passed, including Cloudinary-backed Admin
uploads, existing image-field URLs, duplicate/conflicting assets, manifest-only
transfers with zero database queries, and unchanged database filename values.
`makemigrations --check --dry-run` reports no changes. Cloudinary-mode deployment
checks and legacy URL resolution passed with fixture credentials and no network
upload. Actual Cloudinary credentials, CDN delivery and Render restart persistence
have not been tested against a live account.

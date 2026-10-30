# Scoped catalog transfer: prepared, not applied to production

## Verified source and production observations

At task start, remote master was `b2e3fe758987cc6e67a630b9219184a8e0a1d0f4` (verified).
That commit contains the storefront/footer/navigation/gallery implementation;
`bf21438` contains the earlier checkout/validation/verified-purchase changes.
They are committed and pushed. The local SQLite and IDE changes are separate.

Live premium.css, footer.css, premium.js and product-gallery.js returned HTTP 200
and match pushed source content after normalizing LF/CRLF. This demonstrates
those deployed assets, not every production feature or provider integration.
The public live catalog lists 11 products and its navigation has seven entries:
Bike, Laptop, Phones & Tablets, Power, Smart Tech, Sound Equipment, Watch.
The current local catalog contains 13 products and 13 configured Navigation Items.

No Render CLI/session, configured production database connection or Cloudinary
API credentials were found in the accessible environment. Only `.env.example`
exists; no credential values were printed. Production writes were not attempted.

## Prepared private artifacts

See ignored `.local-backups/catalog-transfer-ready/`:

- `catalog-transfer-package.zip`: allowlisted catalog JSON, comparison/audit
  reports and six missing catalog originals under their exact `media/` keys.
  Contains no SQLite database, accounts, orders, payments, secrets or IDE files.
- `catalog.json`: complete catalog-only source snapshot with internal source
  references. These IDs must be remapped, never inserted as production PKs.
- `local-diff.json`: historical LOCAL baseline comparison, not production truth.
- `media-manifest.json`: 19 referenced image keys, sizes and SHA256 checksums.
- `media-upload-manifest.json`: just the six missing catalog originals.
- `cloudinary-http-audit.json`: public GET status/MIME/original-byte comparisons.
- `verified-existing-catalog-media.zip`: 13 originals whose bytes matched the
  public production copies. This is not a provider-wide Cloudinary backup.
- `rehearsal-plan.json` / `rehearsal-result.json`: isolated local rehearsal;
  43 unchanged + 18 creates, then 61 identical / zero further creates, with all
  non-catalog table fingerprints preserved.
- `storefront-configuration-review.json` / `configuration-media-manifest.json`:
  separate public menu/footer/contact/social review, including one support portrait.
  These are deliberately not consumed by the catalog importer.
- `SHA256SUMS.json`: artifact digests. Rehearsal SQLite/settings files are local
  test fixtures only and are NEVER included in the transfer package.

The snapshot includes 17 categories, 9 brands, 13 products, 1 variant, 4 banners,
5 HomeSections and 12 placements. There are no ProductImage/gallery rows yet.
The gallery upload implementation exists; staff have not populated those records.

Compared with the historical committed LOCAL database, not a production export:

- New categories: Phones, Tablets, Desktop, PC Components, PC Accessories,
  Office Equipment, Appliances, Lifestyle, Security, Networking.
- New brand: AMD.
- New products: iPhone Duo; AMD Ryzen 5 5500 with RX 580 Gaming PC.
- One iPhone Duo Night Sky / 512GB variant, SKU-109114.
- One `iphone Duo` banner, an Apple Collection HomeSection and two placements.
- No substantive changes to the 43 previously exported records. Decimal storage
  formatting differences such as `100` versus `100.00` are not data changes.

Six missing image keys (136,314 bytes total):

```
brands/AMD-01-9412.png
product_images/ihone-duo-star-white-8144.webp
logos/Apple-6176.png
product_images/AMD-Ryzen-5-5500-with-Rx-850-Gaming-PC-9565.webp
variant_images/iphone-duo-night-sky-1252.webp
banners/iPhone-Duo-5279.webp
```

Keep these exact names, including their existing spelling. Cloudinary's backend
uses `gadgetflow/media/<SHA256 of the exact key>` on the currently observed cloud
`nutmfzi6`; changing a key would change its delivery URL.

Review actual owner-entered values before publication: iPhone Duo's base price is
399999, but its only configured variant sells at 419999 (20 variant stock, separate
from base stock 15). The AMD product sells at 62999 with stock 5. The new banner
currently links to `/products/`, not a product detail page. These values and
specifications are preserved as entered; they were not invented or independently
validated against manufacturer/merchant records during this transfer task.

## Safe tools

`catalog_export --output NEW_DIRECTORY [--baseline-sqlite LOCAL_HISTORY]` reads
only Category, Brand, Product, ProductVariant, ProductImage, Banner, HomeSection,
SectionProduct. It does not export auth, orders, payments, sessions, coupons,
business settlement settings, private support requests or policies.

`catalog_import catalog.json` is read-only by default. It matches natural keys,
rejects ambiguity, remaps FK IDs and known internal banner destination IDs,
validates new records and reports creates / identical / preserve_existing.
Existing prices, stock, text and image references are NEVER updated or deleted.
Changed existing records require a separate explicit, field-reviewed reconciliation.
There is no blanket `--update` mode and no full-database `loaddata` step.

Applying requires the reviewed target plan hash, verified backup acknowledgement,
a new target-side catalog backup path, and matching persistent originals. It
rechecks the plan in an atomic transaction and serializes PostgreSQL imports.
Repeated imports do not duplicate rows. There are no new migrations in these tools.

## Exact remaining operator steps

1. Give the agent secure access to the existing Render service/shell and existing
   production database; make the existing Cloudinary API key/secret available in
   process environment, never chat/Git/logs. Keep cloud/prefix consistent with
   production. Cloud name alone is not an upload credential. A public storefront
   URL and GitHub push access do not grant database or Cloudinary write access.
2. On the existing production database, inspect schema and provider backups.
   Make and verify a provider-level database backup, plus required media backups,
   retaining them securely off the ephemeral service. Run `showmigrations shop`
   and `migrate --check`; review/apply only genuinely pending migrations after
   backup. Never restore the local SQLite database over production.
3. Ensure these tested transfer commands are present on the existing service
   before running them (they are new source files from this preparation task).
   Export a fresh target-side catalog snapshot and reconcile it with the source:

   ```sh
   python manage.py catalog_export --output /tmp/gadgetflow-production-catalog-before
   python manage.py catalog_import /secure-transfer/catalog.json > /tmp/gadgetflow-catalog-plan.json
   ```

   Download the production snapshot/plan to secure storage. The currently prepared
   local comparison is insufficient to approve production writes. Inspect every
   target match and different_fields entry. If duplicates, identity changes or
   conflicting production edits appear, stop and resolve them explicitly.
   Pause concurrent catalog editing during reconciliation/apply. The PostgreSQL
   advisory lock serializes these import commands; it does not lock out Admin
   editors. Customer orders are not imported or changed by this operation.
4. Securely unpack the catalog transfer package. In a process configured for the
   EXISTING Cloudinary backend, run the existing media tool. Without --upload this
   only validates originals; with --upload it conditionally copies exact keys and
   verifies bytes. It never changes DB references or overwrites assets:

   ```sh
   python manage.py transfer_media --source /secure-transfer/media --manifest /secure-transfer/media-upload-manifest.json
   python manage.py transfer_media --source /secure-transfer/media --manifest /secure-transfer/media-upload-manifest.json --upload
   ```

   Required environment names: MEDIA_STORAGE=cloudinary, CLOUDINARY_CLOUD_NAME,
   CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_MEDIA_PREFIX. Use existing
   configured values. Stop on conflicts/errors; do not switch to a different cloud.
5. Re-run the production catalog dry-run. Only after reviewing that SAME target's
   plan, matching all media originals and verifying backups, apply missing rows:

   ```sh
   python manage.py catalog_import /secure-transfer/catalog.json --apply \
     --expected-plan HASH_FROM_REVIEWED_TARGET_DRY_RUN \
     --backup /secure-backups/gadgetflow-catalog-immediately-before.json \
     --media-manifest /secure-transfer/media-manifest.json \
     --production-backup-verified
   ```

   The backup path must not already exist. Retain/download it. Re-running a dry-run
   should now show no further creates. Do not use the local rehearsal plan hash.
6. Reconcile public Navigation Items, footer groups, verified contacts and social
   links separately using `storefront-configuration-review.json` and Admin. Reuse
   existing records; do not overwrite newer live values. Transfer the support
   portrait through the existing media tool with its separate configuration
   manifest and original local media, then set the same key on its owned link.
7. Verify live product search/detail pages using actual TARGET product IDs,
   category/brand filters, the banner destination, variant price/stock/image and
   all image GETs (HTTP 200 + image MIME + original bytes). Also run:

   ```sh
   python manage.py inspect_media --http --origin https://farhan-gadgetflow.onrender.com --fail-on-error
   python manage.py catalog_import /secure-transfer/catalog.json
   ```

   Repeat image checks after a normal deployment to verify persistence. Do not
   create production orders/payments or send test notifications to customers.

## Accurately unfinished earlier requirements

The recent design/static/gallery code is pushed and locally verified, but the
original wider checklist was not wholly completed: conditional delivery rules and
delivery estimator, order-item-bound return/warranty processing, full Admin sales
reporting, dedicated base-product model/SKU/box-content fields and complete COD
cancellation stock-release behavior remain outstanding. Provider-backed sandbox
payment verification, SMTP/password-reset delivery, scheduled reconciliation/stock
alerts and production PostgreSQL concurrency/persistence checks need actual access
and configuration. Draft business policies still require approved content.
No live-payment setup, real transactions, customer notifications, production DB
backup, production catalog import or new image upload was performed here.

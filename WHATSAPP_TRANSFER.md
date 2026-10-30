# Catalog and WhatsApp follow-up, 2026-10-30

## Findings

The checkout, catalog, footer and gallery source is already on `master`.
The working SQLite database and uploads differ from the committed database.
Pushing source does not import these rows or upload originals to Cloudinary.
Do not commit/replace the database or assume a deployment migrates its contents.

Fresh anonymous GETs on the existing Render service returned:

- `/` and `/products/`: 200, with 11 catalog products and no WhatsApp shortcut.
- `/products/?q=iPhone+Duo`: 200, no products.
- `/products/?q=AMD`: 200, only the existing ASUS laptop mentioning AMD.
- `/product/14/` and `/product/15/`: 404. These are LOCAL IDs, not assumed target IDs.
- The six new catalog originals listed in CATALOG_TRANSFER.md and
  `business_profiles/farhan-whatsapp-portrait.png`: 404 at their exact hashed
  Cloudinary delivery keys on cloud `nutmfzi6`, prefix `gadgetflow/media`.
- Existing footer CSS and JS: 200. The widget implementation is deployed;
  its absence is consistent with missing/unverified production BusinessLink data,
  not missing client code. Production rows cannot be inspected without DB access.

Local: 13 products, 9 brands, 17 categories, 1 variant, zero gallery rows,
4 banners, 5 active sections, 12 placements and 13 navigation items.
The missing public products are iPhone Duo and AMD Ryzen 5 5500 with RX 580 Gaming PC;
AMD is the new local brand. Ten additional local categories are listed in
CATALOG_TRANSFER.md. Public live navigation still exposes seven legacy categories.
No application catalog cache is configured; the unfiltered catalog queries all
products. Relationships and homepage curation explain additional visibility:

- AMD has `featured=False`: it belongs in filters/catalog, not the featured brand strip.
- Both new products have `featured=True`, but Featured products has explicit old
  placements, which take precedence over that flag. Neither new item is placed there.
- iPhone Duo belongs to Phones & Tablets, not the separate empty Phones category.
  The active category-based Phones & Tablets section should include it after import.
- The Apple Collection section explicitly contains the two older Apple products,
  not iPhone Duo. Desktop has no homepage section. These choices are preserved.

The existing widget is `BusinessLink(kind='whatsapp', is_verified=True)`, with
destination `https://wa.me/8801300972960`, portrait key above, label WhatsApp,
position zero. The general contact phone ends in **2969**, while the configured
WhatsApp destination ends in **2960**; never substitute one for the other.
There is no separately stored widget greeting/enabled setting: verification enables
it, the template contains “How can we help? / Chat on WhatsApp”, and URL `text`
is the optional outgoing message. No outgoing text was configured locally.
The resolver now preserves configured text, or adds the explicit default
“Hello GadgetFlow, I need help with a product.”, URL-encoded, using only the
configured international WhatsApp number. It refuses invalid destinations.

## Prepared artifacts and verification

Ignored `.local-backups/current-transfer/` contains a consistent SQLite backup
(`local-before.sqlite3`), a fresh catalog export, `whatsapp.json`, exact media
manifest, media dry-run, local no-op previews, live GET audit and browser audit.
`gadgetflow-scoped-transfer.zip` contains only the allowlisted catalog,
WhatsApp configuration and 20 distinct original images. It includes existing
catalog originals for validation, not only the seven missing uploads. It contains
no database, customers, orders, payments or secrets. Keep these artifacts private.
The earlier isolated catalog rehearsal remains in
`.local-backups/catalog-transfer-ready/`: 18 creates, 43 unchanged; second run no-op.
That is historical LOCAL data, not a production dry-run or production backup.

`manage.py check`, all 167 shop tests and collectstatic passed. New tests cover
destination/greeting encoding, verification gating, portrait rendering, guarded
insert/repeat, conflict preservation, stale plans and missing media refusal.
Headless Chrome checked homepage and product detail at 1440, 390 and 320 widths,
top/purchase/footer, portrait load and dismissal. Floating comparison stays above
the widget and its close button; both hide while a purchase form or dialog is visible.
The comparison control remains fixed when the footer enters view to avoid collisions.

## Production procedure once access is available

Use the EXISTING Render service/database and Cloudinary account. No replacement
database, service purchase or payment changes are required. Provide access through
secure process environment/provider login, never chat or committed files:

- Existing Render service shell or authenticated API/session.
- Current production DB access and verified provider backup stored off-service.
- Existing `MEDIA_STORAGE=cloudinary`, `CLOUDINARY_CLOUD_NAME`,
  `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `CLOUDINARY_MEDIA_PREFIX`.

Follow CATALOG_TRANSFER.md steps 2–5 for backup, schema review, target export,
target dry-run and insert-only catalog apply. The package uses `catalog/catalog.json`
and `catalog/media-manifest.json`. Pause catalog/support editing during apply.
Do not use the historical rehearsal hash or local no-op hash on production.
Stop on conflicts and reconcile them individually; importer preserves existing data.
Use target IDs from the resulting production export for all final URLs.

After securely extracting the new package into `/secure-transfer`, first upload
only the seven missing originals (the tool refuses differing existing originals):

```sh
python manage.py transfer_media --source /secure-transfer/media --manifest /secure-transfer/missing-media-manifest.json
python manage.py transfer_media --source /secure-transfer/media --manifest /secure-transfer/missing-media-manifest.json --upload
```

Then export and preview the WhatsApp settings on the SAME production database:

```sh
# If production has exactly one WhatsApp link, retain this separate source-format backup:
python manage.py whatsapp_transfer --export /secure-backups/production-whatsapp-before.json
# Always preview; output includes the current target rows, differences implied by
# preserve_existing, and hash. The apply step saves a target snapshot even if empty.
python manage.py whatsapp_transfer /secure-transfer/whatsapp.json
```

If there are no current WhatsApp rows, export reports an error; the provider backup
and the preview's empty target plus apply snapshot document the empty state.
If preview says `create`, review the number, verification state, labels and portrait.
Then, with verified provider DB/media backups retained securely off-service:

```sh
python manage.py whatsapp_transfer /secure-transfer/whatsapp.json --apply \
  --expected-plan HASH_FROM_THIS_TARGET_PREVIEW \
  --backup /secure-backups/whatsapp-immediately-before.json \
  --production-backup-verified
python manage.py whatsapp_transfer /secure-transfer/whatsapp.json
```

Repeat preview must be `identical`. If it says `preserve_existing`, no write is
allowed: inspect the production link in Admin and reconcile the specific fields,
preserving newer values. The command never changes contact/payment/store settings
or existing WhatsApp rows and never uses source primary keys. It verifies portrait
bytes in target storage before inserting; PostgreSQL imports take an advisory lock.

Navigation/footer directory differences are separate content: use the earlier
`storefront-configuration-review.json` for explicit Admin review, not blanket seeding.
Verify the new catalog products, AMD brand filter, category section, variant,
and original images (200 + image MIME + original hashes). Verify the widget's
portrait, encoded `wa.me/8801300972960` URL, dismissal, keyboard focus and mobile
spacing. Repeat after redeploy. Do not open WhatsApp/send messages or place orders.

Without production access, no target backup, target dry-run, import or media upload
can be claimed. Git push and static asset deployment do not complete that work.

# Shopping experience upgrade — local review

This change has not been committed, pushed or deployed by the agent. Migration
`0021_shopping_experience` was applied to the local database after a SQLite backup
in ignored `.local-backups/shopping-upgrade/`. Existing catalog/order records are
retained; new delivery areas and component specifications are not seeded into the
real store. Git push alone does not transfer these configuration records.

## What customers can use

- Product delivery calculator with configured area rates and business-day estimates.
  Checkout requires a valid active area when areas exist, recalculates the charge
  on the server and snapshots the area, charge and estimate on the order. Cart and
  checkout label totals before delivery until an area is selected. With no areas,
  the existing store-wide shipping charge continues to apply; no ETA is invented.
- Guest checkout without creating hidden customer accounts. Guest order details,
  tracking and payment actions require the originating browser session. Knowing an
  order number or matching an email does not grant access. Existing account orders
  retain their ownership checks. New signup from the same browser can attach its
  guest orders to the newly created account. Existing per-account coupons still
  require sign-in. Clearing cookies/signing out can remove guest order access.
- Warranty summaries near the price, replacement conditions and box contents from
  verified Product Warranty records. Existing coverage and claim instructions remain.
- Received → Confirmed → Preparing → Packed → Shipped → Delivered progress, with
  actual staff-recorded event timestamps and an optional validated courier link.
  Cancellation and awaiting-payment states do not pretend steps were completed.
- Optional customer product photo per review (JPEG/PNG/WebP, at most 5 MB), retaining
  the existing paid + delivered purchase evidence for the Verified purchase badge.
  Product Q&A requires sign-in; questions stay private until staff answer and publish.
- PC Builder with live server-rendered totals and catalog/variant options. All six
  core components are required. Checks cover supplied socket, RAM generation,
  motherboard/case size, storage interface, cooler socket, integrated graphics and
  PSU power data. Known conflicts block adding the build. Missing specifications
  are explicitly flagged for store confirmation; this is not a complete hardware
  compatibility guarantee (BIOS, dimensions, capacity, connectors and thermals need
  review). Adding a build validates all cart lines before changing the session;
  checkout still reserves stock and validates current prices atomically.
- Product/ProductGroup JSON-LD based on actual prices, stock and reviews, product
  canonical/social metadata, `/sitemap.xml`, `/robots.txt`, and noindex on private
  checkout/order/tracking pages. Unknown stock and nonexistent ratings are omitted.
  Google reference: https://developers.google.com/search/docs/appearance/structured-data/product-snippet
- The owner's existing WhatsApp portrait is also included as a static asset. When
  the known legacy portrait media URL fails, it falls back to these same original
  bytes. Other missing contact portraits fall back to the WhatsApp icon. This will
  become available on the live site only after the owner deploys the changes;
  Cloudinary originals should still be uploaded through the live Admin.

## Configure real store information in Admin

1. **Delivery zones:** enter approved area names, charges and minimum/maximum
   business days; activate only areas that the store actually serves.
2. **Products → Warranty:** enter verified coverage, replacement terms and box
   contents. Only records marked verified appear publicly.
3. **PC components:** assign real individual catalog products to component kinds
   and fill manufacturer-verified specifications. Use consistent socket/interface/
   form-factor labels. Do not classify a complete desktop as an individual part.
   Product variants are selectable with their actual variant prices and stock.
4. **Product questions:** review the customer's question, write an answer and mark
   published. Unanswered/unpublished questions are not shown on the storefront.
5. **Orders:** update fulfillment status and courier information. COD collection
   and online payment verification continue to use their existing authorized paths.

## Review locally

- Main local store: `http://127.0.0.1:8000/`.
- Isolated sample preview: `http://127.0.0.1:8001/pc-builder/`.
  A visible preview banner identifies sample rates, parts, warranty and customer
  content. Its database and copied media live under ignored `.browser-preview/`.
  Browser checkout checks create sample orders only there.
- Screenshots and browser report: `.browser-preview/commerce-*.png` and
  `.browser-preview/commerce-browser-audit.json`.

Validation: 190 Django tests pass, including guest order/payment/tracking privacy,
duplicate checkout handling, area charges and snapshots, review photos, moderation,
safe structured data, and PC build conflicts/stock/variants. Migration drift, Django
checks, JavaScript syntax and collectstatic pass. Headless Chrome checks at 1440,
768, 390 and 320 pixels cover responsive layouts, delivery quotes, live build totals,
guest COD checkout, and a blocked-media request exercising the portrait fallback.
No real payment or production change was performed.

To restart the preview using the configured local environment:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) '.browser-preview'
& '.\.venv-new\Scripts\python.exe' manage.py runserver 127.0.0.1:8001 --settings=commerce_preview_settings
```

Before a later production release, the operator must apply migration 0021 to the
existing production database after its normal backup procedure, and enter the real
configuration there. Do not replace production with the local or preview SQLite
database or upload the preview data. Existing startup checks reject pending migrations.

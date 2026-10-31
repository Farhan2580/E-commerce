# Customer shopping tools

The tools use the existing catalog, inventory, cart and checkout service. Migration
`0023_customer_shopping_tools` adds fields and workflow tables without replacing
products, variants, uploaded images or orders. Applied locally after a verified
SQLite backup in `.local-backups/customer-shopping-tools/`. All 533 original records
and original columns across 52 existing tables were checked against that backup.

## Customer features

- **Gadget Finder** (`/gadget-finder/`): budget, purpose and optional category.
  Only verified Product Purpose records and known positive stock qualify. An exact
  available variant must meet the budget; an inexpensive parent price cannot make
  an expensive variant qualify. Results are limited to 30, ordered by price.
- **Variant filters**: storage, RAM, colour, size and warranty are catalog-derived.
  A single variant must satisfy all selected dimensions. Enter variant warranty
  text only after verification; product-level coverage remains in Product Warranty.
- **Delivery and reviews**: existing Delivery Zones, server-calculated checkout
  charges, verified warranty details, review photos and paid + delivered purchase
  badges are retained. No delivery rate, ETA or purchase evidence is invented.
- **Comparison**: actual prices, stock, verified product warranty and individual
  option prices, RAM, storage, colour and warranty appear alongside specifications.
- **Buy Again**: available on order details, including session-owned guest orders.
  Uses current catalog prices, original option name/SKU, and current inventory.
  A missing item/option or insufficient stock leaves the cart unchanged. Checkout
  continues to validate and reserve inventory through the existing service.
- **Return / warranty requests**: order details link to item-specific requests
  after delivery. Customers see public status events and staff updates, never
  internal notes. One open request per item/type is allowed. Store staff review
  eligibility; submitting a request does not approve it or transfer money.
- **My alerts** (`/notifications/`): private in-account price and restock notices,
  mark-read action and price subscription removal. Exact variants are required
  for products with variants. Price targets must be below the current option
  price. Existing stock subscriptions remain manageable in My account.
- **Compatibility checker** (`/compatibility/`): only verified directional
  device/accessory pairings produce compatible or incompatible results. Missing
  data explicitly shows unconfirmed. Verify a product-level pairing only if its
  result applies to **every currently listed variant of both products**. Otherwise
  leave it unverified. Recheck pairings whenever adding or changing variants.
- **Frequently bought together**: explicitly curated verified-compatible pairs.
  This is a store recommendation, not an automatically inferred sales statistic.
  Customers select both variants; both items are validated before changing the cart.
- **Preorders**: order history shows staff-entered stage, estimated arrival,
  advance amount/receipt status, public update and cancellation terms. Customer
  forms cannot edit staff status or mark an advance verified. No new advance
  payment collection flow is introduced.

## Admin

The Admin home links to **Store operations** (`/staff/store-dashboard/`) and
**Catalog CSV import / export** (`/staff/catalog-transfer/`). Staff permissions
are enforced; reconciliation details additionally require payment-attempt view
permission.

- Set a product's **Low stock threshold**. The dashboard lists tracked simple
  product stock and individual variant stock at or below that threshold, including
  zero stock. Unknown inventory is not treated as zero. Pending fulfillment lists
  the oldest 50 orders; these are dashboard alerts rather than push messages.
- Sales show paid/delivered merchandise subtotals; collected order totals include
  delivery and discounts. Completed **Refund Records** require a paid order and
  cannot exceed its collected total, including earlier recorded refunds. Enter the
  actual merchant refund reference. This ledger does not execute provider refunds.
  Current payment attempts are grouped by status and discrepancies are flagged.
- Product/variant price and stock edits, order status edits and preorder tracking
  changes are recorded in **Catalog Activities**, with before/after values and the
  authenticated request actor. Checkout reservations and payment release/retry
  inventory changes record their source order. Background work has no human actor.
  Existing Django Admin history and merchant-payment audit records remain in place.
  Raw SQL or arbitrary `QuerySet.update()` outside the instrumented services bypasses
  model signals; use Admin/CSV or add an explicit activity record for new bulk paths.
- CSV exports cover brands, products and variants, preserving IDs and images.
  Use the exact exported headers. Keep an ID to update or leave it blank to create.
  Import brands, then products, then variants. Category/brand/product values are IDs.
  Up to 200 rows / 2 MB of UTF-8 CSV are accepted. Formula-like text is escaped for
  spreadsheet export and restored on import. Specifications must be a JSON object
  with simple values. Price/stock field validation and permissions apply to every row.
  Preview shows proposed before/after values. Apply revalidates all rows and detects
  records edited since preview; the entire import rolls back on any conflict.
- Configure suitability in **Product Purposes** (also inline on products), pairings
  in **Compatibilities**, fulfillment requests in **Service Claims**, and financial
  receipts in **Refund Records**. Populate only approved real data.

## Scheduled alerts and deployment

Run the following with the deployment's configured Python interpreter from a
regular scheduler, for example every five minutes:

```text
python manage.py process_shopping_alerts
```

This generates in-account notifications with duplicate suppression. A price target
triggers only while the selected item has known positive stock. With working SMTP,
use `process_shopping_alerts --email` to additionally send restock and price emails.
It uses `EMAIL_HOST`, `DEFAULT_FROM_EMAIL`, SMTP credentials and `STOREFRONT_URL`.
Unconfirmed or failed sends remain pending. Email delivery can repeat if a worker
crashes after SMTP accepts a message but before the database commit; exactly-once
email delivery is not guaranteed. Do not schedule both stock commands separately.
No recurring scheduler or production email service was configured by this change.

Before deploying, back up the production database, apply migrations through `0023`,
run the normal static asset collection and configure the real store records and
alert scheduler there. Do not replace production with local/preview SQLite data.
No production deployment, real refund, payment or customer email was performed.

Browser fixtures and screenshots are isolated under ignored `.browser-preview/`,
using `shopping-tools.sqlite3` and the visible sample-data banner. They are not
live catalog additions.

Validation: all **210 Django tests** pass, including 17 new shopping-workflow tests.
Django checks, migration consistency and static collection pass. Headless Chrome
checked eight pages at 1440, 768, 390 and 320 pixels (32 checks), with no JavaScript
exceptions or page-level horizontal overflow. Sixteen screenshots and the browser
report are in `.browser-preview/tools-*.png` and
`.browser-preview/shopping-tools-browser-report.json`. Physical phones and other
browser engines were not exercised. No performance benchmark was performed.

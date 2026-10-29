# GadgetFlow storefront

See [SHOPPING_FEATURES.md](SHOPPING_FEATURES.md) for the latest comparison, wishlist and automatically opening cart drawer, including live removal/empty states and keyboard behavior.

For the later premium design, coupons, comparison, quick view, dashboard and stock-alert upgrade, see [PREMIUM_STOREFRONT.md](PREMIUM_STOREFRONT.md). Its startup commands and verification notes supersede the earlier continuation notes below.

## Continuation review (2026-10-30)

The working tree already contained the catalog/admin expansion, checkout service, compatibility migrations, responsive storefront and database changes described below. These were retained. Before further edits, the existing 20 Django tests passed. The remaining design and wishlist gaps addressed in this continuation were the flat shared surfaces and hearts that did not display saved state or update in place.

Shared surfaces now use layered shadows, a soft page gradient and perspective on real product imagery. Product cards lift on fine-pointer hover and keyboard focus; reduced-motion preferences disable the movement. Uploaded promotional artwork is retained.

Wishlist buttons display the current customer's persisted state on catalog, detail and dynamically loaded section grids. POST requests update all visible hearts for the same product, prevent overlapping submissions for that product, and report failures. Anonymous requests go to sign-in. Ordinary form submission remains available without JavaScript. A removed item stays visible until the wishlist page is refreshed, allowing it to be saved again.

Verification for this continuation: 21 Django tests pass, including wishlist JSON responses, saved-state rendering, customer isolation, CSRF, POST-only access and form fallback. Browser visual verification of these latest changes remains outstanding. No migration or write to the store database was performed in this continuation.

Still requiring store-owner input: verified contact/policy text, real tracked stock quantities, and payment credentials if an online gateway is wanted. The current manual-payment flow remains as documented below.

The existing Django application, URLs, catalog records, order records and uploaded media are retained. No external frontend framework or animation dependency was added. The current store uses the black header, wide search, banner/sidebar arrangement, image-led category tiles and compact shopping sections observed on applegadgetsbd.com at desktop and mobile sizes. Promotional layouts are original GadgetFlow HTML/CSS using the store's own product images; reference-site artwork was not copied.

## Run locally (PowerShell)

```powershell
Set-Location 'C:\Users\ASUS\PycharmProjects\E-commerce'
& '.\.venv\Scripts\python.exe' manage.py migrate
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/admin/. Use your existing admin account. If you need a new admin account, create it yourself with:

```powershell
& '.\.venv\Scripts\python.exe' manage.py createsuperuser
```

The configured SDK at implementation time was `.venv\Scripts\python.exe` (Python 3.15.2). Existing requirements were retained.

## Manage the store in Django Admin

- **Banners:** upload a complete banner or select a real product for the original text/image layout. Set the title, description, button label, working local/HTTPS link, active flag and position. Carousel navigation is manual; it does not autoplay. Initial banners use existing products.
- **Home sections:** set the title, optional category and position. Product placements can be ordered with the inline position field. Explicit placements take priority; otherwise the category's descendants are used, or products marked Featured. Category tabs filter within that section. Sections are limited to twelve displayed products and link to the full catalog.
- **Categories:** set the parent, image, featured flag and position. Category filters include descendants. Missing tile images fall back to a real product image. Cycles are rejected by Admin validation.
- **Brands:** edit real brand names, logos, featured flags and positions. The data migration identifies only explicit existing brand names; inspect these associations if you rename or change catalog items.
- **Products:** manage price, optional original/compare-at price, stock, brand, specifications, featured status and position. Specifications accept a JSON object such as `{"Display": "6.1 inches"}`. Additional images and variants are managed inline.
- **Variants:** enter the actual option name, SKU, price, optional original price and stock. Products with variants require a valid option. Prices and stock displayed by the selector match the option checked by the server. Catalog “From” prices use the cheapest available variant when any are in stock.
- **Offers:** keep the existing title, description and image; optionally associate products, mark Exclusive, or provide a working local/HTTPS link. A marketing title does not invent a discount. Savings are calculated only from actual compare-at and selling prices.
- **Store settings:** enter verified contact details, shipping charge, policies and optional manual bKash receiving number. Contact details and policies are intentionally left blank rather than fabricated. Shipping is a single configured amount per nonempty order; its default is zero, matching the former checkout's absence of a shipping charge.
- **Orders:** purchased names, variants, SKU, prices and totals are retained as snapshots. Payment verification is an explicit staff action in Admin, not a customer-supplied field.

## Inventory and payments

Existing records had no stock data. Their stock remains **blank / untracked**, and the UI says “Availability confirmed with order.” They remain purchasable to preserve existing behavior. Enter real quantities in Admin to enforce stock limits; zero disables purchase. Newly created variants have zero stock until a quantity is entered. Do not enter invented inventory.

Cash on delivery works without external credentials and creates an unpaid/pending order. Manual bKash submissions become available only after a receiving number is configured in Store settings. Sender number and transaction reference are required; the order remains **Manual payment review** until staff verify the transfer. This site does not initiate a transfer or declare a transaction successful.

There was no online bKash gateway in the original project. A future gateway integration would require the merchant's app key/secret, API username/password, sandbox/production endpoint and approved callback URL, followed by server-side execution and verification. Merely entering a receiving number does not enable a gateway. No real payment was performed during implementation.

## Checkout and data preservation

- Cart values contain product/variant identities and quantities, never trusted client prices. Legacy session-cart shapes are read compatibly.
- Add, update, remove, clear, wishlist, review and checkout changes use POST with Django CSRF protection. Existing mutation URLs are retained; direct GET links to them intentionally return 405.
- Checkout validates current quantities and inventory, recalculates product savings and configured shipping, and writes the order, stock changes and item snapshots in one transaction. Conditional stock updates prevent negative stock. A unique checkout token prevents duplicate orders and repeated stock decrements. Retrying an old checkout cannot clear a newer cart.
- SQLite serializes writes. A temporary write conflict returns a retryable checkout error rather than pretending the order succeeded. The same submission token can be retried.
- Order details, order-success pages, history, wishlists and preorders are scoped to the signed-in customer.
- Migration `0003` snapshots the product names currently available for historical items; it cannot reconstruct names from before this change. Existing totals and rows are preserved.
- The old database also contained an unmanaged `Product.logo` column and lacked the preorder table recorded in `0001`. A compatibility preflight in `0002` registers/preserves that column before SQLite table rebuilds. `0005` reconciles databases that had already applied the intermediate schema. The local logo paths were restored exactly from the backup; no uploaded files were changed.
- A pre-migration SQLite backup is in `.local-backups/`. Browser flows used `.browser-preview/browser.sqlite3`, a disposable database copy. No browser test orders or users were added to the real store. Uploaded media was not replaced. Both local-artifact directories are ignored by Git.

## Verification

```powershell
& '.\.venv\Scripts\python.exe' manage.py check
& '.\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '.\.venv\Scripts\python.exe' manage.py migrate --check
& '.\.venv\Scripts\python.exe' manage.py test shop --noinput
```

Focused tests cover cart totals/quantities/CSRF, variant ownership and prices, stock validation, transaction rollback, idempotent checkout, order snapshots and ownership, manual payment status, wishlist privacy, search/filter/sort/pagination, category tabs, reviews, preorders and safe Admin content.

Chrome was used to inspect the reference and the finished storefront. Local viewport checks covered 1440, 768, 390 and 320 pixels, plus mobile navigation, Escape, keyboard search suggestions, carousel buttons, category tabs, live cart counts, cart quantities, login, variant price/stock changes, gallery, checkout, order confirmation, catalog filters and reduced motion. Screenshots are in `.browser-preview/`. Browser testing covers the local implementation, not every device or a live payment gateway. No push or deployment was performed.

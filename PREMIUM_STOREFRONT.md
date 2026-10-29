# GadgetFlow premium shopping upgrade

The latest comparison, wishlist and cart-drawer behavior, migration and verification are documented in [SHOPPING_FEATURES.md](SHOPPING_FEATURES.md). It supersedes the earlier interaction descriptions below.

## Light design refresh

The current design uses page `#F7F8FC`, white cards/navbar/footer, text `#182230`, primary controls `#FF7A18`, and selective lavender `#EEE9FF`, sky `#E8F4FF`, mint `#E6F7EF`, and peach `#FFF0E5` accents. Shared palette/theme tokens are defined once in `store-components.css`; `premium.css` adds pastel composition, soft shadows and gentle motion. Earlier black header/footer, muddy gradients, image rotation, poster sidebar and extra hero thumbnails were removed. There is one wide hero carousel, with existing offers displayed in their dedicated section. Original uploaded artwork remains unchanged.

Light mode is the default regardless of OS theme or the previous `gf-theme` preference. The early head script reads only the new `gf-theme-v2` key; dark mode persists only after a customer explicitly selects it with the theme button. The HTML/CSS defaults are light even if local storage is unavailable.

Verified in local Chrome: exact colors, old-dark preference migration before stylesheet loading, explicit dark/light persistence, upright proportional imagery, full-width carousel navigation, reduced motion, and no horizontal overflow at 1440, 768, 390 and 320 pixels. Existing Django tests still pass. This refresh makes no schema/data changes.

Implemented in four stages over the existing working tree. Existing URLs, catalog, uploads, reviews, preorders, manual bKash and COD remain in place. No frontend framework or animation package was installed.

## Run locally

```powershell
Set-Location 'C:\Users\ASUS\PycharmProjects\E-commerce'
$env:DJANGO_DEBUG = '1'
& '.\.venv\Scripts\python.exe' manage.py migrate
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/admin/ with your existing account. `DJANGO_DEBUG=1` serves local static assets; it is for local development. Debug defaults to off. `DJANGO_SECRET_KEY` can override the existing development key without a source edit. No credentials were generated, changed or committed by this upgrade.

## Features and controls

1. **Design:** warm-white/charcoal/orange tokens, restrained yellow light, existing black navigation and category hierarchy, layered catalog imagery, gentle floating/parallax, card perspective and lighting, category depth, section entrances, loading states, animated native dialogs and a shopping bag drawer. Dark/light preference is saved in local storage. Reduced motion disables animation and transform effects. Mouse parallax runs only on fine-pointer devices. All product pictures are existing catalog images; uploaded banner artwork stays intact.
2. **Shopping:** quick view loads actual product data and variants; cart writes go through the existing CSRF-protected stock validation. The bag displays server-calculated prices, shipping, coupon discounts and line errors. Quantity zero removes an item. Wishlist saves persist to the customer's account and update all matching visible hearts and the header count. Comparison is session-scoped and limited to four products by the server. It uses real specification keys, prices and availability. Search retains debouncing, keyboard suggestions, category/brand/price filters, sorting and pagination, and adds available/out-of-stock filtering.
3. **Customer account:** add, edit or delete addresses, select an owned address for checkout, open recent orders and the wishlist, and manage stock alerts. Recently viewed products come only from this browser session's actual detail-page visits. Related products share the current product's exact category and are labeled accordingly; neither list is a fabricated recommendation.
4. **Admin:** existing banners, featured categories, product sections, placements, links and section order remain editable. Variants retain existing names/SKU/prices/stock and gain optional color, storage and size fields. Offers gain optional start/end dates; expired/future offers are excluded and a countdown appears only when a real end date exists. Offer banners describe promotions; they do not independently invent a price discount. Configure actual selling/compare-at prices or a coupon for monetary discounts.

## Coupons and checkout

Use **Admin → Coupons** to set an uppercase code, active flag, percentage/fixed amount, dates, minimum eligible item value, global usage limit and per-customer limit. Optional products and exact categories are combined with OR; when both are empty the entire catalog is eligible. Category descendants must be selected explicitly. Optional customers restrict account eligibility.

The cart accepts an applied coupon; a blank code removes it. Checkout also accepts a code and has **Review coupon & total**, which calculates a preview without placing an order. An invalid/expired coupon blocks order placement until corrected or removed. Coupons require sign-in, exclude shipping, apply to current selling prices and are capped at the eligible subtotal. Only one code applies at a time. No example coupon was inserted into the real database.

Checkout recalculates discounts and inventory inside the existing atomic order transaction. Coupon reservation, redemption, item snapshots, order creation and stock updates roll back together on failure. The unique checkout token continues to prevent duplicate orders and stock decrements. Coupon usage counts placed orders, including orders later cancelled; it is not automatically refunded by a fulfillment change. Redemption history and financial snapshots are read-only in Admin.

Staff update fulfillment using **Orders → Status**. Each Admin status change records a dated event visible in the customer's timeline. Payment verification is separate: changing fulfillment does not mark payment paid. Historical orders receive no invented event timestamps; their detail pages explain when events were not previously recorded. Saved address edits do not change existing order addresses.

## Stock alerts and missing email setup

Signed-in customers can request an alert for a specific out-of-stock product or variant and supply the receiving email address. Repeated requests update the same subscription. Variant ownership is checked. Subscription cancellation is restricted to the owner. Untracked stock is not treated as evidence of a restock.

Set these process environment variables using your own SMTP provider:

```powershell
$env:EMAIL_HOST = 'your-smtp-host'
$env:EMAIL_PORT = '587'
$env:EMAIL_HOST_USER = 'your-smtp-user'
$env:EMAIL_HOST_PASSWORD = 'your-smtp-password'
$env:DEFAULT_FROM_EMAIL = 'your-verified-sender'
$env:EMAIL_USE_TLS = '1'
$env:EMAIL_USE_SSL = '0'
$env:STOREFRONT_URL = 'https://your-store-domain'
& '.\.venv\Scripts\python.exe' manage.py send_stock_alerts
```

Use TLS or SSL according to your provider, not both. No `.env` loader is installed: set environment variables in the shell or service configuration. The command refuses to send without `EMAIL_HOST` and `DEFAULT_FROM_EMAIL`. Run it through your scheduler after inventory updates or periodically. It sends only pending alerts for positively tracked available stock, reserves each subscription before sending, marks sent only after the email backend confirms, and leaves failed sends pending for retry. As with ordinary SMTP, a process failure after delivery but before the database commit can cause a retry email; this is not an exactly-once delivery guarantee. No real stock emails were sent during implementation.

COD and manual bKash retain their existing behavior. Configure the manual receiving number in Store settings. An automated payment gateway still requires merchant credentials and a separate verified integration. No payment success was simulated and no live transaction was performed.

## Data preservation

Migrations `0006_premium_shopping_features` and `0007_stock_alert_subscriptions` add fields/tables; they do not delete, reseed or replace catalog/order data. They were applied locally after SQLite's backup API created `.local-backups/premium-before-20261029-202428.sqlite3` (UTC filename). The local preservation manifest verifies every original column/row in all 25 original tables. Only expected new Django content types/permissions were added. Product logos, prices, order items and uploads remain preserved.

Browser fixtures and the COD test order exist only in `.browser-preview/premium-browser.sqlite3`. `.browser-preview/` and `.local-backups/` are ignored by Git. Nothing was pushed or deployed.

The final audit also confirmed no preview users/products in the real database. An already-open storefront session updated browsing-history/expiry bookkeeping during the work; its original cart and authentication values were preserved. No live customer activity was reverted.

## Verification

```powershell
& '.\.venv\Scripts\python.exe' manage.py check
& '.\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '.\.venv\Scripts\python.exe' manage.py migrate --check
& '.\.venv\Scripts\python.exe' manage.py test shop --noinput
node --check shop/static/shop/store-components.js
node --check shop/static/shop/premium.js
```

All 33 Django tests pass, along with Django system/migration checks and JavaScript syntax checks. Tests cover cart totals, quantities, variants, stock, rollback, duplicate checkout, snapshots, customer ownership, CSRF, coupon eligibility/dates/minimum/caps/usage, comparison limits, browsing history, scheduled offers, address ownership and stock-alert delivery/failures. Mail tests use an in-memory backend.

Local Chrome was exercised at 1440px desktop and 390px/320px mobile widths. Verified: saved theme, keyboard search, category tabs, correct first product-grid column after AJAX updates, comparison, variant quick view, cart quantity updates/removal and totals, modal/menu Escape, wishlist count/state, saved address checkout, coupon preview, COD order confirmation with unpaid status, variant SKU, stock-alert subscription and reduced motion. No JavaScript exceptions occurred in those flows. Screenshots are in `.browser-preview/premium-*.png`. Real SMTP, a live payment gateway, production hosting, physical touch devices and other browser engines were not tested.

## Changed implementation areas

- `shop/static/shop/premium.css` and `premium.js`: design, theme, motion, dialogs and cart interactions.
- `store-components.js`, shared navbar/card/assets/product-grid partials, base/home/catalog/detail/cart/checkout/profile/order/offer templates: integrated controls and states.
- `shop/models.py`, `forms.py`, `views.py`, `services.py`, `context_processors.py`, `urls.py`, `admin.py`: backend rules, customer ownership and Admin management.
- `shop/migrations/0006_*.py`, `0007_*.py`, `management/commands/send_stock_alerts.py`, `tests.py`, and `djangoProject13/settings.py`: additive schema, notifications, verification and environment configuration.

Remaining store setup: enter real inventory and variant attributes, verified business/policy information, actual coupon/offer rules and SMTP settings/scheduling. No scarcity, discounts, reviews, service promises or sales activity were fabricated.

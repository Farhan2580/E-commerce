# Comparison, wishlist and cart drawer polish

These changes extend the existing systems and preserve the bright light theme, existing URLs, catalog, orders, uploaded media and checkout service.

- **Comparison:** up to four real products, persistent selection order, accurate counts, explicit add/remove actions and POST-only clearing. Deleted/duplicate selections are normalized. Missing or blank specifications display “Not provided”; valid zero values remain visible. The comparison page updates without navigation and has a keyboard-accessible horizontal table with sticky labels on small screens.
- **Wishlist:** the existing database model and unique customer/product constraint are retained. New heart forms use idempotent save/remove actions; legacy toggle POSTs still work. Saved state persists across sessions, and responses update hearts, accessible labels, counts and the wishlist empty state immediately. Guest hearts and the guest wishlist page provide sign-in links. All queries and changes use the authenticated customer, ignoring submitted user IDs. Available items use the existing cart actions; variants can be chosen through quick view or details.
- **Drawer:** successful Add to Cart opens the existing dialog, including from quick view. It displays actual product/option images, names, SKU, quantities, unit prices, line totals, shipping, existing coupon adjustments and total. Quantity buttons, direct entry and removal use the original cart endpoints and validation. Successful and rejected writes return authoritative server-rendered drawer and cart-page content. Requests are serialized within a page; other tabs refresh through storage events. Browser-history restoration refreshes shopping state. Loading failures offer Retry and a full-cart link, preserving the count instead of showing a false empty state.
- **Accessibility:** native modal behavior plus explicit Tab/Shift+Tab wrapping, Escape, background scroll locking, opener focus return, focus restoration after line changes, live feedback, mobile layout and reduced-motion support.

Migration `0008_variant_cart_image` adds one blank optional `ProductVariant.image` field, editable through the existing Admin variant inline. Supply real option images when available; otherwise carts use the product image. The migration was applied locally after a SQLite backup in `.local-backups/variant-image-before-20261029-205647.sqlite3` (UTC filename). All original rows/columns in the 32 non-session tables were checked unchanged. No images or catalog rows were seeded or replaced.

On another checkout/database, apply the migration before starting:

```powershell
& '.\.venv\Scripts\python.exe' manage.py migrate
$env:DJANGO_DEBUG = '1'
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

Verification: all **37 Django tests** pass; `manage.py check`, migration consistency checks and JavaScript syntax checks pass. Focused tests cover wishlist persistence/ownership/duplicate saves, comparison limits/normalization/clearing/missing values, CSRF, cart quantities/stock, variant image fallback, totals and coupon consistency. Existing checkout/inventory tests remain green.

Local Chrome checks covered guest sign-in links; four-product limits and in-place comparison clearing; wishlist save/remove/count/empty states; quick-view Add to Cart automatically opening the drawer; cross-tab drawer/cart-page synchronization; rejected stock changes; keyboard focus, Tab and Escape; offline load failure/retry; a complete 320px mobile drawer and scrollable comparison; reduced motion; and the drawer-to-checkout flow producing a correctly priced unpaid COD order. No JavaScript exceptions occurred. Screenshots are in `.browser-preview/shopping-*.png`. Fixtures/orders were created only in the disposable preview database. Physical touch devices and other browser engines were not tested. Cross-tab push refresh uses browser local storage; cart-page visibility and browser-history restoration also fetch current server state.

Main changed areas: `shop/services.py`, `views.py`, `context_processors.py`, `urls.py`, `models.py`, `tests.py`; migration `0008`; shared shopping JavaScript/CSS; and the comparison, wishlist, product-heart, drawer, cart-page and base/navbar templates. No deployment or Git push was performed.

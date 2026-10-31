# GadgetFlow Admin workspace

Open `/admin/` after restarting the Django server. The existing staff accounts,
permissions, Admin URLs and database records continue to be used. This redesign
requires no database migration and adds no external theme package or CDN assets.

## Where to work

| Section | Main tasks | Customer-facing connection |
| --- | --- | --- |
| Catalog | Products, categories, brands, warranties, suitability, compatibility | Product pages, filters, Gadget Finder, comparison and accessory pairings |
| Orders & delivery | Orders, preorders, delivery areas | Checkout charges, order history, courier tracking and preorder progress |
| Payments & promotions | Merchant receipt review, refund records, coupons | Existing payment verification and checkout discounts |
| Customer support | Returns, warranty requests, inbox, questions, reviews, alerts | Customer request timelines, product answers, reviews and notifications |
| Storefront & content | Navigation, banners, homepage collections, offers, policies, FAQs | Customer menus, homepage, footer and published information |
| Store settings | Store details, verified contacts and outlets | Store identity, enabled checkout methods and contact information |
| People & access | Users and permission groups | Existing customer and staff accounts |
| History & records | Activity, order items, coupon usage, saved products/addresses | Supporting records linked to their original customers and orders |

Dashboard counts link to the actual filtered Admin lists: low inventory, pending
fulfillment and open return/warranty requests. Counts and shortcuts respect the
current staff account's permissions. The operations and CSV tools remain linked.
Search the dashboard directory or sidebar to find a tool. On smaller screens,
use the logo/Home link to return to the full directory.

## Editing order

1. Create categories and brands, then add products.
2. Fill product identity, base prices, photos, descriptions and display order.
3. For products with variants, set each option's own price, stock, RAM, storage,
   colour and warranty in the **Product options** section. The parent stock does
   not replace variant inventory. Maintain verified warranty and suitability below.
4. Connect those existing categories/brands to **Main navigation** and products
   to **Homepage collections**. Do not create duplicate product records for display.
5. Review order/payment records before updating fulfillment and courier tracking.
   Existing payment verification guards and COD collection permissions still apply.
6. Handle item-specific customer progress in **Returns & warranty requests**.
   **Support inbox** is for enquiry assignments and internal notes.

## Developer file map

| File | Responsibility |
| --- | --- |
| `djangoProject13/admin_apps.py` | Selects the custom site through Django's supported `AdminConfig.default_site` hook |
| `shop/admin_site.py` | Site branding, permission-aware dashboard counts and shared context |
| `shop/admin_navigation.py` | Single section/label/description map for both dashboard and sidebar |
| `shop/admin_helpers.py` | Connected form guides and inventory/fulfillment/request filters |
| `shop/admin.py` | Existing model registrations, grouped fields, inlines and authorized actions |
| `shop/experience_admin.py` | Shopping-tools registrations, CSV import and operations dashboard |
| `shop/templates/admin/` | Admin layout, directory, navigation and connected form guide |
| `shop/static/shop/admin/workspace.css` | Admin-only responsive styles and light/dark colours |
| `shop/static/shop/admin/workspace.js` | Local dashboard directory search; no business data writes |

To add an Admin tool, register its `ModelAdmin` normally and optionally add its
`app_label.ModelName` to `SECTIONS` in `admin_navigation.py`. The map starts with
Django's permission-filtered registered models; it never grants access itself.
Unmapped future models stay available under **Other tools**. To add a guided form,
extend `WorkspaceAdmin`, define its help text and declare related links with their
required permissions. Keep payment, stock and order rules in their existing
models/services rather than copying business logic into templates or JavaScript.

Existing Product gallery-upload permissions, protected payment fields, review
actions and inline form names are retained. Django's related-object controls,
search, filters, history, validation and CSRF handling remain native.

## Validation and release

All **217 Django tests** pass, including seven tests for navigation completeness,
staff/add-only permissions, actionable counts/filters, connected forms and payment
field protection. Browser checks cover seven pages at 1440, 768, 390 and 320 pixels
(28 layout checks), directory/sidebar filtering, empty search, keyboard Escape,
login and dark mode. No page-level horizontal overflow or JavaScript exceptions
were observed. Screenshots and report are under ignored `.browser-preview/admin-*`.
Browser records use the separate local preview database; no real customer order
was created or edited for this design review.

Django checks, migration consistency, JavaScript syntax and static collection
pass. For deployment, restart the application and run the usual `collectstatic`.
Earlier shopping-tool migrations are still required on deployments that have not
applied them. This design has not been deployed to production.

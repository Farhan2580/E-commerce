# Collection landing pages — local implementation

All thirteen Navigation Items continue to use the existing named product_list
route with category/brand query parameters. No duplicated storefront or separate
payment/cart implementation was introduced. Production deployment has not been verified.

## Presentation and Admin

The shared catalog template now includes a contextual hero, breadcrumb, collection
heading/introduction, collapsible sidebar, product count, sort toolbar, three-column
desktop cards, responsive mobile cards and numeric pagination. Existing product
detail, quick view, cart, variants, wishlist and compare actions are retained.

Admin > Navigation Items supports optional hero_image, page_title, introduction.
Banner uploads use configured persistent storage and storage-generated URLs.
When no approved banner exists, the hero uses GadgetFlow styling and up to three
actual images from that collection. Empty collections have a text hero and an
honest empty state. No competitor banner, logo, certification, product, previous
price, stock quantity or claimed 144-item count was copied from the references.

Configure actual product variants (color/storage/size) in Product Admin and use
scalar specification entries such as RAM, Model, Processor, Generation, Network,
Region, SIM, Type, Edition, Plug, Body or Warranty only when verified. Facet groups
and checkbox values are derived from actual scoped records, not invented options.
Unknown filter names/values produce an empty result instead of broadening scope.

Variant dimensions are applied together against the same variant row. Different
specification dimensions use AND; multiple checked values within a group use OR.
Filters, stock availability, current prices and sorting run server-side. Search
within a long facet list is client-side and changes no selection by itself.
Pagination and sorting preserve multiple selected values. Reset filters preserves
the current collection scope. English-only behavior remains enforced.

## Data and checks

A consistent local SQLite backup with integrity `ok` was created before migration
under ignored `.local-backups/catalog-pages-before-*.sqlite3`.
Migration 0019_collection_page_content adds three optional NavigationItem fields.
It was applied locally; no catalog data was seeded, recategorized or overwritten.
Existing unrelated uncommitted files and local database changes were preserved.

- Full shop suite: 150 tests passed. New coverage includes all 13 menu targets,
  scoped real facet values, matching variant combinations, JSON specification
  filtering, invalid values, prices, stock, sorting, escaping, empty states and
  multi-select preservation through sort/pagination.
- Django checks passed; makemigrations --check --dry-run found no changes.
- JavaScript syntax check and git diff --check passed.
- Actual local GET requests to all thirteen menu targets: HTTP 200 with heroes.
- Chrome 1440x1100, 768x1024, 390x844 and 320x844: no horizontal overflow,
  no JavaScript exceptions, actual hero images loaded. Sidebar is expanded on
  desktop and collapsible/initially closed on smaller screens.
- Screenshots: ignored `.browser-preview/catalog-*.png`.

Reference screenshots had many product/specification records absent from this
catalog. Supply genuine products, variants, approved collection banners and
English introductory copy through Admin to populate those sections. This release
does not fabricate those missing business details or claim a live deployment.

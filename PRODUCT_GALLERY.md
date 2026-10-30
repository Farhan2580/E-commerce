# Product images and details

Implemented and verified locally. Production deployment has not been verified.

## Upload and manage pictures

Admin > Products > open a product > **Upload gallery images** lets staff select
multiple pictures in one file picker. Save appends them after existing images.
Up to 20 images may be selected per save, each at most 10 MB; supported formats
are JPEG, PNG, WebP and GIF. Repeated saves can add further gallery images.
Every selected file is validated before the product form is saved; a corrupt
file prevents a partial batch. Existing original files are never overwritten.

The existing **Product images** inline remains available for single uploads,
caption/alt text, position and purpose. Choose **Description image** to place an
actual approved image in the description section instead of the thumbnail gallery.
Gallery images default to the existing purpose. Staff need both product access
and add_productimage permission to use the bulk upload field.

All uploads use the configured Django ImageField storage. Existing Cloudinary
integration, original file paths and storage-generated URLs remain in use; no
collectstatic or DEBUG changes were made for these uploaded files.

## Storefront

- Main, gallery and actual variant pictures form one deterministic image list;
  duplicate URL references are shown once. A product with gallery pictures but no
  main picture still displays its first gallery image.
- Active thumbnails have an orange outline and accessible current state.
- Clicking the main picture opens a native modal viewer with previous/next,
  arrow-key navigation, Escape close and focus return. Mobile horizontal swipes
  change the main picture without preventing normal vertical scrolling.
- Real variant option pills keep the original select control and server cart
  identity. Choosing a variant updates price, original price, SKU, stock, maximum
  quantity, matching picture and enabled cart state. No imaginary combinations
  are added. Clearing the selection restores the initial display.
- Quantity +/- buttons only edit the quantity field; they do not submit the cart.
  The selected stock limit and server-side stock validation remain enforced.
- Specification, description, verified warranty and review links go to real
  sections. Unverified warranty, EMI, delivery deadlines, deposits and unsupported
  product claims from reference screenshots were not copied.

## Data preservation and validation

Consistent local backup before migration: ignored
`.local-backups/gallery-before-*.sqlite3` (integrity: ok).
Migration `0020_product_image_purpose` adds a default-gallery purpose field;
existing image rows/paths are preserved. No real product pictures were fabricated
or attached to existing customer-facing records during browser testing.

Tests cover multi-file Admin uploads, original-file preservation, image decoding
and HTTP image responses, all-or-nothing validation, permission boundaries,
gallery-only products, description/variant image separation and duplicate references.
Existing shop tests continue to cover cart/variant stock and ownership behavior.

Browser functional fixtures exist only in ignored
`.browser-preview/gallery-preview.sqlite3` with separate media storage on port 8001.
Chrome at 1440, 390 and 320 pixels verified thumbnail switching, viewer navigation,
Escape/focus return, matching variant price/image/stock/cart identity, quantity
boundaries and no horizontal overflow or JavaScript exceptions. Real local product
pages were also inspected on port 8000. No production orders, payments or customer
notifications were created. Real product images must be supplied by store staff.

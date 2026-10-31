# Reference product-page layout

The product page follows the owner's screenshots: compact brand/Compare row,
inline price, actual saving amount, availability and SKU; outlined Colour/Storage
option groups; pill-shaped quantity controls; WhatsApp and delivery information;
and accessible Specifications, Description, Warranty, Reviews and Q&A tabs.

## One source of product information

- Brand images come from **Admin → Catalog → Brands → Logo**. The Brands list
  and editor now include a logo preview. The product page links to that brand's
  collection; homepage brand tiles already use the same logo field. Missing or
  failed logo images fall back to the brand name. Existing uploaded logos are
  reused; no replacement logo or brand data was generated.
- **Products → Product options** supplies exact Color, Storage, RAM, Size and
  Warranty values. Attribute chips are shown only when their complete attribute
  tuple identifies exactly one database variant. Missing/ambiguous attributes
  retain the exact configuration selector and named-option buttons instead.
- The initial grouped selection uses the same lowest-priced available variant
  as the displayed product price. Unavailable combinations clear the exact variant
  and disable purchasing. Out-of-stock variants remain visible and disable buying.
  Price, savings, SKU, stock limit and product photo update together. All cart and
  checkout endpoints continue to validate the selected product/variant server-side.
- Delivery areas, verified product warranties and verified WhatsApp links use
  existing Admin data. No EMI offer, prebooking amount or fixed delivery ETA was
  added from the screenshot; those commercial terms are not configured records.
- Without JavaScript, the exact variant select and all information sections remain
  usable. Tabs support arrow keys, Home/End, fragment links and review-form errors.

Main files: `shop/product_presentation.py`, product purchase/brand-mark includes,
`shop/static/shop/product-options.js`, `product-reference.css`, and the existing
product view/gallery/price handlers. No database migration is required for this
presentation change. Run the normal static collection and restart the application
when deploying it.

Validation: **221 Django tests pass**. Browser checks at 1440, 950, 390 and 320 px
exercise uploaded logos, exact option prices/SKUs, absent combinations, zero stock,
stock quantity limits, keyboard tabs, cart insertion, the existing iPhone Duo page,
broken-logo fallback and JavaScript-disabled fallback. No page-level horizontal
overflow or JavaScript exceptions were observed. Preview fixtures and screenshots
are isolated under ignored `.browser-preview/product-reference-*`; sample option
prices/stock were not written into the real catalog. No live deployment was made.

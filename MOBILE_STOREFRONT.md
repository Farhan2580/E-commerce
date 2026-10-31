# Phone storefront refresh

Local changes only. No commit, push or deployment was performed by the agent.
The phone stylesheet is restricted to viewports at most 760px and loads after
the existing page styles. Desktop shopping layouts retain their existing design.
There are no model or migration changes.

## Customer experience

- Compact header with a large search field and consistent touch controls.
- SVG bottom navigation for Home, Browse, Bag, Wishlist and Account, with the
  current section highlighted and the bag count using the existing cart updates.
- Simple Main Menu with a black header, flat category rows, small chevrons and
  light submenu backgrounds, following the owner's reference. Only one category
  expands at a time. All products and PC Builder remain as shortcuts immediately
  below the menu header. Other store links follow the category list. The native modal
  retains its backdrop, keyboard focus containment, Escape and focus return.
- Shorter promotional/collection areas, one-row service shortcuts and a swipeable
  two-row category directory so customers reach products sooner.
- Two-column product cards on narrow phones, swipeable home product rails and
  uncluttered controls. Compact phone cards keep Compare at the image's top corner
  and Quick view at the image's lower corner, without adding a separate action row.
  Cards are approximately 298–312px tall. Quick view supports variant selection and the existing add-to-bag flow.
  Customers can also open full product details through the image/title. Comparison remains accessible
  through each card and the Browse menu, without an always-floating empty counter.
- Mobile catalog filter sheet with native modal focus handling and real existing
  filter fields. Sort remains on the catalog toolbar. Resizing to desktop restores
  the same filter form to the sidebar. Without JavaScript the native filter details
  and normal sort submit button remain usable.
- Product gallery sizing, readable information and a fixed purchase bar above
  navigation. This bar invokes the existing form, respects required variant
  selection, syncs the selected price/disabled state and opens the existing bag.
  It hides when the original purchase button is visible or a modal is open.
- Compact WhatsApp portrait shortcut on browsing pages; product/purchase pages
  keep their purchase controls clear. Existing original portrait fallback remains.
- More readable cart/checkout controls. The checkout item list can collapse on
  phones and stays expanded on desktop, bringing delivery/payment fields forward.
- Safe-area spacing and 16px form inputs; floating controls hide when the visual
  viewport indicates a text-entry keyboard. Native dialogs support keyboard
  operation; animations respect the existing reduced-motion preference.

## Verification

The full 190-test Django suite passes. Related shopping, commerce, English-language,
navigation and static-file tests were also rerun after the final checkout template
change. JavaScript syntax, static collection and whitespace checks pass.

Headless Chrome checks cover 320, 390, 430, 760 and 1440px widths for home, catalog,
product and builder layouts, with no page-level horizontal overflow. Interaction
checks cover category expansion and Escape/focus return, filter application and
desktop restoration, mobile search, theme switching, sticky add-to-bag, required
variants, selected price updates and synchronized bag counts. Shopping interactions
use the separate preview database on port 8001. Main-store screenshots on port 8000
use browsing only. These are browser viewport checks, not physical-device tests.

Screenshots: ignored `.browser-preview/phone-home.png`, `phone-catalog.png`,
`phone-product.png`, `phone-menu.png`, and `mobile-after-checkout.png`.
Browser report: `.browser-preview/mobile-browser-audit.json`.

Review on `http://127.0.0.1:8000/` using the browser's device toolbar; refresh to load
the new assets. The sample-data preview remains at `http://127.0.0.1:8001/`.

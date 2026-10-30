# GadgetFlow dark footer

Implemented and verified locally; production deployment is unverified. The supplied written layout brief was
used because reference image attachments were not available in the conversation.
Only the footer is dark; the storefront palette and existing Inter font remain.

## Admin setup

- Store settings: tagline, verified support phone/email/address. The explicitly
  supplied public phone 01300972969 is the fallback when no verified phone exists.
  This number never enables WhatsApp or payment acceptance.
- Outlets: actual name, address, optional hours, public HTTPS map URL, visibility
  and position. Only visible records with an address and valid HTTPS map appear.
  The footer shows up to three and links to the complete `/outlets/` page.
- Information pages: English title is the link label; position controls order.
  Publish substantive English content only after approval. Existing combined
  Shipping & Delivery, Returns & Refunds and Warranty & Exchange can cover the
  corresponding policies without creating conflicting copies. Optional separate
  exchange, preorder, return/refund, corporate, blog, press and careers page types
  are available. Put corporate/blog/press/careers in the Company footer group.
  Working contact, tracking, FAQs and payment-method pages stay connected.
- Complaint / Advice uses the existing Contact Us form with validation, CSRF,
  rate limits, duplicate-safe persistence and staff-only review. Tracking retains
  account ownership checks. No new notification or chatbot integration was added.
- Business links: publish verified HTTPS social profiles, a separate WhatsApp
  link containing the actual configured WhatsApp number, or genuine published
  app links. Facebook, Instagram, LinkedIn and YouTube receive matching SVG
  icons; other existing verified profiles retain an accessible link icon.
  WhatsApp links use wa.me/api.whatsapp.com/web.whatsapp.com; app links use
  apps.apple.com or play.google.com. Unverified links remain hidden.
- Footer groups: rename/reorder/hide directory columns and select actual
  categories, brands and active Home sections (curated collections). Category
  and brand labels/order reuse those records. No automatic sales rankings exist.
  A group with no renderable links is hidden. Prefetching prevents one query per
  footer link. Collections must be active to appear.

Optional initial directory configuration is repeatable and never creates catalog
records or alters existing groups:

```powershell
& '.\.venv-new\Scripts\python.exe' manage.py configure_footer_directory
& '.\.venv-new\Scripts\python.exe' manage.py configure_footer_directory --apply
```

Preview was reviewed and applied locally: Mobile Phones, Accessories, Top Brands.
No matching Home Appliances or curated Trending/Best-selling records were found.

## Data and verification

Local backup before migration:
`.local-backups/footer-before-20261030-180352.sqlite3` (integrity check: ok).
Migrations 0015 and 0016 add outlet/directory structures and optional choices;
they do not delete/reseed products, orders, accounts, uploads or policy content.
Both were applied locally. Existing unrelated edits remain in place, including
the earlier local static fix, IDE configuration and database changes.

- Django checks: passed; makemigrations --check --dry-run: no changes.
- Full shop suite: 140 tests passed, including published-link visibility,
  ordering, outlet visibility, filtered catalog URLs, app/social gating, English
  publication, payment badges and unchanged support-form behavior.
- Local CSS: HTTP 200, text/css; source asset serving remains enabled only in
  development settings. JavaScript syntax and git diff --check passed.
- Chrome at 1440x1100 and 390x844: footer rgb(8,8,8), light body
  rgb(247,248,252), no horizontal overflow; desktop groups open, mobile groups
  collapsed. Screenshots are in ignored `.browser-preview/footer-*.png`.
- Every displayed internal footer URL was fetched successfully; protected links
  led to login. No real forms, orders, payments or notifications were submitted.
- Payment badges continue to reflect enabled methods, retaining sandbox labels.

Still needed for fuller publication: verified support email, actual outlet
addresses/map URLs/hours, WhatsApp number/profile URL, social URLs, genuine app
listing URLs, approved policy/company copy, and any curated collection choices.
No missing information was fabricated or published as a placeholder.

Start locally:

```powershell
& '.\.venv-new\Scripts\python.exe' manage.py runserver 127.0.0.1:8000 --settings=djangoProject13.development
```

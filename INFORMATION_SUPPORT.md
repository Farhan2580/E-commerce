# Information and customer support

The customer storefront is now English-only. Language controls are removed and
saved Bangla preferences are normalized to English. The existing language POST
URL remains compatible but selects English. Customer text never falls back to
Bangla-only fields; published policy URLs remain reachable with an English
availability message when English copy is missing. Bangla database fields and
their contents remain intact and editable in Admin for future use.

This extends the existing GadgetFlow policy URLs, order/status history, Store settings, checkout phone validation, shipping charge and payment logic. The light design, shopping features, customer accounts, orders and uploaded media are retained. No Size Guide, payment gateway, public guest order lookup, analytics script or fabricated business policy was added.

## Public pages and drafts

| Page | URL | Initial state |
| --- | --- | --- |
| Contact Us | `/information/contact/` | Published; verified phone **01300972969** and working contact form |
| Track Your Order | `/track-order/`, `/track-order/<id>/`, `/information/tracking/` | Published; authenticated owner only |
| FAQs | `/information/faqs/` | Published; six factual/live answers, four business-dependent draft questions |
| Payment Methods | `/information/payments/` | Published; enabled methods only |
| Shipping & Delivery | `/information/shipping/` | Draft outline |
| Returns & Refunds | `/information/returns/` | Draft outline |
| Terms & Conditions | `/information/terms/` | Draft outline; no legal clauses invented |
| Privacy Policy | `/information/privacy/` | Draft with inspected implementation facts and review checklist |
| Cookie Policy | `/information/cookies/` | Draft with actual runtime cookie/storage inventory |
| About Us | `/information/about/` | Draft outline |
| Warranty & Exchange | `/information/warranty/` | Draft outline and verified product-warranty listing |

Drafts return 404 to the public and are absent from the footer. Staff with the Information page view permission can preview a draft with `?preview=1` or Admin's “View on site”. Publication exposes its existing URL and footer link; returning it to Draft hides both. Customer Care and Company / Account retain operational/account links. The Policies column appears when at least one substantive policy is published, rather than linking to empty drafts.

The seed migration preserves any nonempty previously published legacy shipping/returns/privacy text in the corresponding Information page. Original Store settings policy fields remain intact and read-only in Admin; the Information page is now the editing source. The current local legacy fields were blank, so all seven policy/company pages remain drafts.

## Admin workflow

- **Information pages:** English/Bangla titles and body, Draft/Published status, footer group/order, private editorial notes, last-updated date, and inline bilingual sections. All requested topic headings are pre-created. Empty section bodies are never shown publicly. Save substantive content first, then publish; non-operational empty pages cannot be published through validation. Review the private checklist before publication. Plain text is escaped; HTML/scripts are not executed.
- **FAQs:** group, English/Bangla question/answer, publication status, order and update date. Dynamic answer sources read live payment/shipping settings or the real tracking/support behavior. Delivery deadlines, cancellation, returns and authenticity assurances are draft until supplied. Search supports the two languages and current dynamic answers. Native `details` accordions work without a JavaScript dependency.
- **Store settings:** verified phone/email/address flags, bilingual address/support hours, registration/license text plus verification, current shipping charge, COD enable flag and the existing manual bKash receiving number. Unverified email/address/license values are hidden publicly. Missing values are omitted. **Business links** holds verified WhatsApp, Messenger, map and social URLs, with bilingual labels; links must use public HTTPS without embedded credentials. A phone number does not automatically enable WhatsApp. Maps are links, not automatic third-party embeds.
- **Orders:** staff may assign courier name, tracking number and an HTTPS tracking URL. Existing fulfillment status changes continue to write dated events. Tracking shows only real events; it does not invent transit updates or poll a courier API. Customer ownership is required even for staff using the public tracking view. Staff's normal Admin permissions remain separate.
- **Product warranties / Product warranty inline:** actual warranty type, period, coverage, exclusions, claim steps, service phone/email/address and verification flag. Only verified entries appear on product details/the published warranty page. Existing catalog specifications remain unchanged; no warranty is inferred from marketing descriptions.
- **Support requests:** contact, warranty-enquiry and owner-bound order support all use one model. Staff can view the reference, submitted fields, account/order association, preferred language and created/updated timestamps, and manage status (`New`, `In progress`, `Resolved`, `Spam`), assignee and private notes. Submitted identity/message/order fields are read-only. Public users cannot list or retrieve requests by an ID. Contact forms save to Admin; they do not automatically send email or promise a response time.

## Language and publication

The English/বাংলা switch is present in information-page headers and the footer. It uses a CSRF-protected POST, stores only the information-language preference in the existing Django session and permits safe local return URLs. Support-page UI/form labels and content are bilingual. Missing Bangla body/section text falls back to English with a notice. No automatic translations or invented address/team details were inserted. Existing storefront/catalog/account UI is retained; this is not a machine translation of the whole store.

## Checkout consistency

`StoreSettings.shipping_price` is still the one flat charge per nonempty order. Shipping pages/FAQ read it at request time. There is no conditional free-delivery threshold in checkout; establish a matching checkout rule before publishing one. A zero configured charge is displayed as a numeric amount, not a promise of delivery coverage.

`enabled_payment_methods()` is shared by checkout, the order service and support pages/FAQs. COD defaults to its existing enabled behavior and can now be explicitly disabled. Manual bKash appears only with a configured public receiving number. Disabling both methods prevents order placement. Sender number/reference remain required for manual bKash, which retains manual-review status. Fulfillment changes do not verify payment. No gateway credentials are rendered, and no payment success or real transaction was simulated.

## Forms and abuse controls

Contact and order-support forms validate name, phone, email and a 10–5000-character message; order support is bound to an owned order on the server, not a submitted customer/order ID. Forms use Django CSRF protection, a hidden honeypot, signed two-hour tokens bound to the session and form purpose, and unique submission tokens for duplicate-safe saves.

Rate limits are shared database counters: **5 POST attempts per source IP/hour**, plus **10 per authenticated account/hour**. Invalid/honeypot attempts count as attempts. Only keyed IP/account hashes are stored, not raw IP addresses or forwarded headers. A limit returns HTTP 429; a temporary write conflict returns retryable HTTP 409. `REMOTE_ADDR` is used deliberately; a deployment behind a reverse proxy needs a reviewed trusted-client-IP configuration before changing this behavior. Untrusted forwarded headers are ignored.

Run expired-hash cleanup periodically, for example hourly or daily:

```powershell
& '.\.venv\Scripts\python.exe' manage.py clear_support_limits
```

This deletes only expired rate records, never support submissions. Submissions, orders, preorders/uploads and customer records have no newly invented automatic retention/deletion schedule. Define the business retention process before publishing that part of the privacy policy.

## Privacy/cookie audit

Inspected active views, checkout/services, models, base template and shared JavaScript. The draft describes account/password hashes; order/contact/delivery/payment-reference data; saved addresses/wishlists; reviews; preorders and uploads; coupon redemptions; opted-in stock emails; support messages and optional account/order association; session cart/comparison/browsing/language/form state; and hashed abuse counters.

The Cookie page reads actual session/CSRF cookie names and ages from Django settings (currently `sessionid`: 14 days; `csrftoken`: 364 days). Functional local storage uses `gf-theme-v2` for the chosen theme and `gf-shopping-change` for tab synchronization signals. Language adds no new cookie. The active storefront has no optional analytics/marketing scripts, so no empty consent banner was added. If those scripts are introduced later, they need consent gating and withdrawal before activation.

Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`) is an actual external font dependency and is disclosed in the drafts. SMTP provider, hosting/logging practices, courier processors, retention and production HTTPS/cookie configuration require owner review. Current local settings do not establish production HTTPS-only cookies; no broader security or legal-compliance claim is made. Contact saves do not send email. Configured social/map/courier destinations open only when followed; no map embed or courier API was added.

## Data preservation and validation

Migrations `0009_information_and_support` and `0010_seed_information_drafts` are applied locally. SQLite backup: `.local-backups/information-before-20261029-215051.sqlite3` (UTC filename). The audit compared original columns/rows in all **32 non-session tables**, allowing only the supplied phone/verification and new Django model metadata. Catalog/order prices, customers, legacy policy values and uploads were preserved. New courier fields are blank for existing orders; no historical events were fabricated. Seed data adds only the information structures, known implementation FAQs and the supplied phone. It does not add addresses, licenses, social accounts, delivery promises, authenticity claims or warranties.

All **48 Django tests** pass, including original shopping/checkout tests and new publication, escaping, bilingual fallback, form persistence/idempotency/validation/CSRF, spam/token/rate, verified-detail, FAQ, payment, warranty and tracking ownership tests. Local Chrome verified contact persistence in Bangla, language switching, grouped/searchable FAQ accordions, configured-only payments, draft exclusion, sign-in/owner tracking, assigned courier details, staff request visibility, staff privacy preview and actual Admin publication of a disposable About page. Desktop and 390px/320px layouts fit without horizontal overflow; no JavaScript exceptions occurred. Browser users/orders/messages and publication changes exist only in `.browser-preview/support-browser.sqlite3`. Physical devices, other browser engines, live courier services and real payment/email delivery were not tested. Nothing was deployed or pushed.

The final audit allowed normal `last_login` timestamp changes from an existing account signing in during the work. No accounts were added/removed or other account fields changed; no preview accounts exist in the real store. Existing customer activity was retained rather than restored from backup.

## Business information still needed

1. Verified support email, address, support hours, WhatsApp/Messenger/social/map URLs and any license/registration details.
2. Delivery areas, processing/delivery estimates, courier partners, parcel inspection, delays, failed delivery and any free-delivery conditions that match checkout.
3. Cancellation rules, returns/refund deadlines and eligibility, electronics exclusions, packaging/evidence, shipping-cost responsibility, refund methods/timing and exchange terms.
4. Per-product verified warranty type/period/coverage/exclusions, claim steps and service contacts; actual authenticity assurances.
5. Approved brand story, mission and founder/team; reviewed website terms and jurisdiction.
6. Actual hosting/email/courier/payment provider details, retention/deletion periods, customer-request process, production privacy/security review and Bangla translations where missing. Review and publish the policy drafts only when those decisions are complete.

Startup/checks:

```powershell
& '.\.venv\Scripts\python.exe' manage.py migrate
& '.\.venv\Scripts\python.exe' manage.py check
& '.\.venv\Scripts\python.exe' manage.py test shop --noinput
$env:DJANGO_DEBUG = '1'
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8000
```

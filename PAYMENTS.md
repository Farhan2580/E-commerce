# GadgetFlow sandbox payments

The existing checkout had COD and a manual bKash transfer claim; it had no API gateway.
Historical manual bKash orders retain their original method codes and data.
New manual orders require explicit account eligibility and audited verification.
The current checkout presents exactly
three choices: Cash on Delivery, bKash, and Card. New
`CARD` and `ONLINE_BKASH` use **SSLCOMMERZ v4 hosted checkout**, which supports cards
and bKash on accounts provisioned for those channels. No separate bKash API
credentials are needed for this integration. Merchant channel eligibility is not
known: each new choice is unavailable until explicitly configured. Sandbox only;
there is no live endpoint or live-mode switch in this implementation.

Official references consulted:

- https://sslcommerz.com/integration-document/
- https://developer.sslcommerz.com/doc/v4/index.html
- https://developer.sslcommerz.com/registration/

Checkout enablement summary (values belong in the process environment, not templates):

| Choice | Required setup |
| --- | --- |
| Cash on Delivery | Enable COD in Store Settings. No provider credentials. Grant collection staff `shop.change_order` and `shop.record_cod_collection`. |
| bKash | Sandbox SSLCOMMERZ `SSLCOMMERZ_STORE_ID` and `SSLCOMMERZ_STORE_PASSWORD`, `PAYMENT_PUBLIC_URL` pointing to public HTTPS test callbacks, provider activation of the merchant's bKash channel, then `SSLCOMMERZ_BKASH_ENABLED=1`. |
| Card | The same sandbox Store ID, Store Password and public HTTPS URL, provider activation of the specific Visa/Mastercard brands, `SSLCOMMERZ_CARD_BRANDS=visa,mastercard` (only the approved subset), then `SSLCOMMERZ_CARD_ENABLED=1`. An empty/unknown brand list disables Card. |

Both online methods also require migrations, reachable return/IPN endpoints, and
scheduled `manage.py reconcile_payments`. Both default disabled; no real merchant
credentials, live environment, or actual sandbox transaction was used in this repair.

The documented `multi_card_name` parameter customizes the hosted channel list;
Card requests only the configured approved brand groups, and bKash requests `bkash`. The docs say
to omit that optional parameter when customization is not needed. SSLCOMMERZ,
not Django, collects payment instrument information and authenticates customers.

## Required merchant setup (still outstanding)

The receiving number and intended bank account supplied by the owner are stored
in **Store Settings → bKash receiving account / Requested settlement destination**,
accessible only to staff with Store Settings permissions. They are requests, not
evidence of eligibility, ownership, merchant activation or settlement approval.
Do not expose bank settlement information in customer templates or provider
session parameters. Settlement is configured and approved in the provider portal.

Still required from the merchant:

- Confirm the requested bKash account is an owned **Merchant** or **PRA** business
  account. Ordinary personal accounts remain unavailable for this workflow.
- Obtain provider approval for business collection, exact **Merchant Payment**
  instructions for this account, and its current per-payment/aggregate limits.
  Payment and Send Money are not interchangeable. The PRA documentation describes
  receiving customer payments separately from the holder's Send Money feature:
  https://www.bkash.com/en/page/personal-retail-account .
- Supply the bank name, account-holder/legal name, branch, routing number, account
  type/currency and account verification requested by SSLCOMMERZ for the intended
  account ending **0001**. Have SSLCOMMERZ explicitly approve and bind this account
  to the merchant. Merely filling the staff record does not configure settlement.
- Obtain the sandbox Store ID/Store Password, public HTTPS callback origin,
  merchant bKash channel approval and exact activated card-brand list. Separate
  direct-bKash API credentials are unnecessary for the existing SSLCOMMERZ route.

### Optional eligible manual bKash review

Do not enable this to test using real money. It remains disabled for the supplied
number while account type/approval are unconfirmed. In test fixtures only, the
eligible workflow is exercised without any bKash transaction.

To configure an approved workflow, authorized staff must set **all** of:
`bkash_account_type` to Merchant/PRA, `bkash_account_confirmed`,
`bkash_manual_approved`, `bkash_manual_enabled`, the verified receiving number,
exact provider-approved Merchant Payment instructions, and a confirmed positive
`bkash_manual_limit`. Staff must monitor aggregate limits independently. Missing
settings or a personal/unconfirmed account keep manual bKash unavailable.

Online hosted bKash takes precedence when configured. Otherwise the one bKash card
selects the eligible manual route. After the order/reservation is saved, the owner
sees the snapshotted receiving number, copy control, exact server-calculated amount
and `GF<order-id>` reference. No receiving destination is published merely because
someone entered a number in Store Settings.

References are submitted only on an owner-only CSRF-protected endpoint after the
order exists. The immutable claim is **Awaiting verification**, not paid. Duplicate
submission is idempotent; duplicate references across current/historical orders are
rejected. Numeric PIN/OTP-like input is rejected. Screenshots are not collected.

Review staff need `shop.change_order`, `shop.verify_manual_payment` and
`shop.view_manualpaymentclaim`. Open **Manual payment claims → Review merchant
receipt**. Confirmation requires explicit checks of the actual merchant record:
transaction identity, recipient, exact amount/BDT currency, order reference and
non-duplicate receipt. Record the source/findings in the note. Direct payment-state
editing is disabled for bKash orders. Submit/review actions retain actor, timestamp,
decision and note in an immutable admin audit history.

Manual stock/coupon reservations last **24 hours**, and the scheduled
`reconcile_payments` command releases them once if abandoned. A submitted but
unverified reference whose reservation expires becomes a reconciliation review;
it never triggers fulfillment. Rejection releases stock/coupon capacity once.
Late confirmation is blocked after release; staff must resolve/refund externally.
Manual retries cannot open a second charge through the hosted retry endpoint.

### Hosted merchant setup

1. Register a **sandbox** SSLCOMMERZ merchant account. Obtain its Store ID and
   Store Password. Do not use production credentials or share them in messages.
2. Confirm with SSLCOMMERZ that that sandbox Store ID supports the requested
   card groups and bKash; enable only confirmed channels. If this merchant cannot
   receive bKash through SSLCOMMERZ, leave online bKash disabled. A separate direct
   bKash merchant agreement and tokenized integration would then be needed;
   legacy manual orders remain available for staff review meanwhile.
3. Export the variables in `.env.example` into the Django process environment.
   This project does not automatically read `.env`. Set `PAYMENT_PUBLIC_URL` to
   the publicly reachable HTTPS origin of a **test** server. Do not include a
   path, credentials, query string, or fragment. Set each confirmed channel's
   `SSLCOMMERZ_*_ENABLED` to `1`. No credentials were available for an actual
   provider sandbox acceptance test during implementation.
4. On another environment, review and apply migrations with `manage.py migrate`
   after backing up your database. The local database was backed up consistently
   before migrations; this repair also adds migration 0013 for staff account
   configuration and manual-review audit records. Migrations 0011/0012
   were applied during this repair. Migrations 0011 and 0012 preserve existing orders and payment
   values. Migration 0012 preserves old attempts, adds retry history and a unique
   current-attempt constraint, and creates the COD collection permission.
5. Ensure SSLCOMMERZ can POST to `/payments/ipn/<attempt-uuid>/`. The per-attempt
   IPN URL and return URL `/payments/return/<attempt-uuid>/` are sent at session
   creation. Confirm this dynamic IPN URL configuration with the merchant portal
   (the docs also describe portal IPN listener configuration). Do not require a
   customer session or CSRF token on these provider endpoints. All other payment
   mutations require an authenticated owner and CSRF.
6. Schedule `manage.py reconcile_payments` **every minute** on the test host.
   This queries provider state and releases abandoned reservations even if no
   callback arrives. Keep it running: without scheduling, abandoned stock stays
   reserved until an explicit status check. Monitor `review` attempts and the
   command's completion/errors. The command can safely be rerun.
7. Complete sandbox acceptance tests for both enabled channels with the merchant:
   paid, failed, cancelled, pending/timeout, closed browser, delayed and repeated
   IPNs. Use the current provider-supplied test instruments only on its hosted
   page. Confirm actual hosted channel availability; do not infer it from a flag.
   No real transaction, deployment, or live activation is authorized by this work.

## State, identity and inventory

- The existing cart service re-reads product/variant prices, stock, shipping and
  coupons server-side, persists an order and payment attempt in one transaction,
  and reserves stock before provider communication. Totals must meet the documented
  BDT 10–500,000 range. The provider email field supports at most 50 characters.
- Each order has one current attempt, a retained attempt history, and a unique
  30-character provider transaction ID for each attempt.
  The existing checkout token prevents repeated form submissions creating another
  order. Session creation is claimed once with a conditional update. A repeated
  click reuses its hosted URL. An uncertain initiation is never retried, so it
  cannot create another payable provider session; reconcile/wait for expiry.
- A failed/cancelled payment can be retried on the **same order** through the
  owner-only, CSRF-protected retry endpoint. The server queries the original
  transaction first and requires fresh verified closure. Stock and coupon validity
  are checked and reserved again atomically. The original attempt becomes
  historical; a new provider transaction ID is created. Repeated retry requests
  with the same old attempt ID resume the new current attempt. Stale failure
  callbacks cannot change the current order or inventory. A late historical success
  blocks fulfillment for review. Pending, ambiguous, review and unconfirmed expired
  sessions cannot create another charge.
- Return/IPN data is ignored. The server queries its stored transaction ID with
  merchant credentials and independently validates the returned validation ID.
  Success must match transaction ID, order reference (`value_a`), exact amount
  against both attempt and order, BDT currency, bank transaction identity and
  safe risk level. Bank transaction IDs are unique in the database.
- Payment state is separate from fulfillment state. Online orders start at
  `awaiting_payment`; verified safe payments advance once to `received`. Admin
  cannot edit online/manual bKash payment status or advance an unpaid order. Historical
  payment data is preserved; a manual reference is never treated as API verification.
  New manual bKash orders use the audited review workflow above. COD remains unpaid until authorized staff
  use **Record cash collected for selected COD orders** in Order Admin. Grant both
  `shop.change_order` and `shop.record_cod_collection` to collection staff. The
  action ignores online/cancelled/already-paid orders and records the staff user
  in Django's admin audit log. COD payment status cannot be edited directly.
- Checkout method changes keep shipping inputs in place. Submitted delivery
  details are retained in the customer's server-side session for error recovery;
  failed online orders retain their persisted shipping details during retry.
  No shipping or payment secrets are stored in browser local storage. The three
  choices remain visible when unavailable, with disabled inputs and concise availability text.
- Tracked product and variant stock is deducted as a reservation for 30 minutes
  for hosted checkout, or 24 hours for an eligible manual payment.
  Untracked legacy stock stays untracked. Exact reservation targets/quantities
  are persisted; deleting reserved products/variants is protected. Verified
  failure/cancellation releases once, restores coupon capacity and cancels the
  online order. Expiry releases even if the gateway is unreachable. A browser
  cancellation alone cannot release stock while the provider may still charge.
- Verified payments after release become `review`, with no fulfillment or
  stock deduction. Risk/mismatch results also block fulfillment; reservations
  are released at expiry. Multiple successful provider records remain unconfirmed
  and require investigation. Reviews and unexpected late settlements require a
  merchant operator to reconcile/refund in the provider portal; automatic refunds
  and replacement charges are deliberately not implemented. Customer order details
  and the Order Admin payment-attempt inline expose accurate states and issue codes.
- Success is immutable; duplicate notifications do not decrement stock, redeem
  coupons, or create another fulfillment event. Query timeouts keep the order
  unconfirmed. The scheduled command continues querying non-paid attempts so
  late settlements remain detectable; retention/batching can be added at scale.

## Credentials and logging

Secrets come only from environment variables. `.env` and `.env.*` are ignored;
`.env.example` contains placeholders only. Provider requests use TLS verification,
15-second timeouts, a fixed sandbox hostname and no HTTP redirects. Hosted redirect
URLs must use HTTPS on that same sandbox host. No raw payloads, card numbers,
CVVs, PINs or OTPs are collected, logged or persisted. Provider calls raise generic
errors without sensitive exception text, and sensitive local variables are redacted
from Django error reports. `DJANGO_DEBUG` defaults off. Keep it off on any public
test host. Configure proxies/APM to avoid logging callback bodies, outbound
validation query strings (which contain credentials), or full hosted checkout URLs.

## Local verification

Run using the configured project interpreter:

```text
manage.py test shop.test_manual_payments shop.test_payments shop.tests shop.test_support shop.test_staticfiles --noinput
manage.py check
manage.py makemigrations --check --dry-run
```

Tests use an isolated Django test database and mocked provider HTTP responses.
They exercise the real checkout/reservation and verification services; they are
not evidence that merchant credentials or real hosted channels work.

The checkout repair was also checked in Chrome at 1440px, 390px and 320px with a
copied database: three payment cards, disabled/unavailable online states, orange
selection, method-specific instructions/action labels, shipping-field preservation,
duplicate-submit blocking and HTTP 200 CSS responses. Enabled-choice UI checks used
local test-only settings with all provider calls blocked, without submitting online
payments. The local database was backed up and migrated after tests; existing
order/item, product/variant, coupon/redemption, order-event and user rows were
compared with the backup. Static assets were collected. Restart any already-running
local server to load the repaired code.

The merchant-configuration repair added 13 manual/configuration tests (88 total
tests passed), checked official local brand assets with `findstatic`, and repeated
Chrome checks at all three widths. The supplied destinations were saved in local
staff settings after a consistent backup at
`.local-backups/before-merchant-payment-0013.sqlite3` and migration 0013. Existing
order/item, product/variant, coupon/redemption, order-event and user values matched
the backup. Account type remains **unconfirmed**, manual collection is disabled,
and neither hosted method is configured. No approval flags or live credentials
were enabled, and no actual provider sandbox transaction was performed.

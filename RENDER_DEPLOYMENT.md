# Existing GadgetFlow Render service

## Repository audit

Repository: `Farhan2580/E-commerce`; remote default/only branch observed: `master`.
Root directory: repository root (contains `manage.py`). Backend Python, WSGI/ASGI,
templates, source CSS/JS, all fourteen shop migrations and requirements are tracked.
This is a Django-rendered full-stack application, not a separate frontend build.
No existing build/start scripts or Render blueprint were tracked before this repair.
Actual Render dashboard commands/linked branch have not been inspected without access.
Do not create a second service or purchase resources to apply these instructions.

`db.sqlite3` and some old bytecode were already tracked in earlier commits. This
repair does not include database bytes or delete the production database; .gitignore
now excludes SQLite files from future additions. Ignoring a tracked file does not
untrack it. Back up the current production database and establish durable storage
before any separate removal from repository history/tracking. No history rewrite
is necessary or authorized. Never stage `.env`, keys, backups, `.venv` or local DBs.

## Existing service settings

Confirm these in the existing Render service, keeping its URL and payment settings:

| Setting | Value |
| --- | --- |
| Linked branch | Verify `master` on the existing service |
| Root directory | Empty/repository root |
| Build command | `bash render-build.sh` |
| Start command | `bash render-start.sh` |
| `DJANGO_SETTINGS_MODULE` | `djangoProject13.settings` |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_SECRET_KEY` | Existing strong production key; preserve it |
| `DJANGO_ALLOWED_HOSTS` | `farhan-gadgetflow.onrender.com` plus any existing custom hosts, comma-separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://farhan-gadgetflow.onrender.com` plus any existing HTTPS custom origins |
| `DATABASE_URL` | Existing persistent PostgreSQL connection URL |
| `DATABASE_USE_URL` | `1` only after backup and production data reconciliation |
| `DATABASE_SSL_REQUIRE` | `1` (default) |
| `MEDIA_STORAGE` | `s3` or `cloudinary` |
| S3 variables | Bucket/region/credentials/endpoint/prefix from PRODUCTION_MEDIA.md |
| Cloudinary variables | Alternative to S3: see CLOUDINARY_MEDIA.md; no AWS variables required |
| `STOREFRONT_URL` | `https://farhan-gadgetflow.onrender.com` |

Do not paste secrets into commits/logs/chat. Keep all current payment configuration;
do not enable live payment channels. The build only installs requirements and
collects application static files. It does not move media, seed content, run
migrations or replace a database. Startup checks persistent storage and DEBUG,
requires migrations already applied, then runs the existing WSGI app with Gunicorn
on Render's assigned PORT. Source templates and design remain unchanged.
On Render, proxy HTTPS is recognized and session/CSRF cookies are secure. This
preserves valid HTTPS Admin and checkout form origins behind Render's TLS proxy.

`DATABASE_URL` was previously ignored by settings. It is now parsed explicitly
when `DATABASE_USE_URL=1`,
with PostgreSQL TLS and connection health checks. With no URL, local development
still uses local SQLite. The Render deployment check rejects that fallback. Do not
point at a new empty database simply to pass the check: first preserve/migrate the
CURRENT production data, including users/orders/payment records. This code does
not migrate data between SQLite and PostgreSQL. That requires a verified backup,
an inventory, a controlled transfer and reconciliation under operator access.

No paid database/bucket is provisioned by this change. Reuse existing services;
if none exist, the account owner must select/setup them before activating scripts.

## Backup and migrations

Before applying migrations or importing content, use the production provider's
backup facility. For PostgreSQL, an operator with access can run `pg_dump` against
the existing connection, storing the backup securely outside the repo. For an
existing SQLite deployment, take a consistent SQLite backup (not a copy of the
local development database), and preserve all files under the current MEDIA_ROOT
before any restart. Verify backups are readable/restorable.

In Render Shell against that SAME production database:

```sh
python manage.py showmigrations shop
python manage.py migrate --plan
```

Review only the pending operations against the backup. Existing migrations include
historical data operations; never fake/reset/re-run applied migrations. No new
schema migration is introduced by this repair. After review and backup:

```sh
python manage.py migrate --noinput
python manage.py migrate --check
```

Where the existing Render plan supports a pre-deploy command, run the reviewed
migration command there. Otherwise run it manually in Render Shell before starting
this release. Startup fails visibly if schema changes are pending. Do not run
migrations against an unknown/empty replacement database or use local SQLite as
a production restore. Production migration status cannot be inferred locally.

## Catalog comparison and scoped import plan

Read-only public audits found the same eleven product card names locally and live.
No missing catalog rows were demonstrated, so no import or reseed was performed.
Public HTML cannot establish complete DB equality, hidden/draft rows, configuration,
stock or user/order contents.

If the operator finds missing catalog rows after inspecting the live database:

1. Export affected production catalog models to a secure backup, excluding users,
   orders, payments, coupons and business/payment settings. Include categories,
   brands, products, variants/gallery, banners/offers, sections and placements as
   needed. Keep a separate provider-level DB backup too.
2. Prepare an explicit proposed insert list, matching categories/brands by their
   unique name, variants by unique SKU, products by reviewed name+category+brand,
   and placements by destination section+product. Abort ambiguous matches. Use
   target IDs from these matches, never local primary keys.
3. Skip existing matched rows; do not overwrite prices, inventory, images, text,
   offers or existing relationships. Add only reviewed missing rows, in a single
   transaction, with a dry-run count and a second-run no-op check. Do not use
   `loaddata` on a full local database dump.
4. Copy referenced original images through the conditional S3 transfer command,
   retaining their keys and rejecting byte conflicts. No placeholders.
5. Review before applying and compare counts/names/keys afterwards. The plan must
   be based on the real production inventory, not guessed from the local DB.

## Media and live verification

Follow PRODUCTION_MEDIA.md for exact key mapping and upload transfer. Source media
exists locally, but no bucket access is currently available to perform transfer.
Category/product/banner/offer templates already use ImageField storage URLs.
Any production-only Admin uploads must be recovered from the live storage, not
assumed present in the local media directory.

```sh
python manage.py check --deploy --tag files --tag database --tag security
python manage.py inspect_media --http --fail-on-error --origin https://farhan-gadgetflow.onrender.com
python tools/audit_storefront.py https://farhan-gadgetflow.onrender.com
python tools/verify_media_http.py https://farhan-gadgetflow.onrender.com --extra-url /media/categories/ACTUAL_NEW_UPLOAD.png
```

Public audit uses GET only: home, catalog, offers, cart, category filter and product
detail, plus same-origin CSS/JS hashes. Anonymous checkout should redirect to login.
Authenticated checkout rendering needs an authorized account; do not submit the
checkout form or call payment endpoints. Image verification requires status 200,
image MIME type and valid decoded bytes, including the original three failing URLs.
Repeat a real Admin-uploaded category check after redeployment to prove persistence.

GitHub Actions now runs Django checks/tests/collectstatic on push. If the existing
Render service uses 'After CI Checks Pass', wait for this check; if it uses 'On
Commit', monitor Render directly. A GitHub CI success does not prove a Render
deployment. No Render API/service credentials are available here to read actual
build/start settings, env vars, production migration state or deployment logs.

References: https://render.com/docs/deploy-django and https://render.com/docs/deploys

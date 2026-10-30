# GadgetFlow storefront and gallery publishing checkpoint

This release contains the local static-loading repair, dark footer, configured
navigation infrastructure, collection pages/filters, product sliders, motion
polish, product image gallery and multi-image Admin uploader.

Local validation: 155 Django tests pass; Django checks, migration drift check,
JavaScript syntax checks and collectstatic pass. Browser verification details
are in FOOTER.md, COLLECTION_PAGES.md and PRODUCT_GALLERY.md. The recreated
`.venv-new` interpreter resolves the earlier interpreter blocker recorded in
IMPLEMENTATION_CHECKLIST.md; that document is a historical checkpoint.

## Production operator steps

Publishing code is not proof of a successful Render release. Existing deployment
branch/configuration and production access must be inspected by the operator.
No production database or uploaded-media backup has been verified in this session.
Before production migrations, make and verify backups of the actual production
database and uploads. Do not substitute the local SQLite file for production.

Migrations 0015 through 0020 add the footer/outlet/navigation/gallery structures.
Review `manage.py migrate --plan`, then apply `manage.py migrate --noinput` to the
same existing production database after backup. Existing render-start.sh refuses
to start when migrations are pending. An auto-deploy triggered by a push can
therefore fail its startup check until these migrations have been applied.
The release does not bypass that guard, change production DEBUG, enable live
payments, create a new Render service or purchase resources.

Catalog/navigation/contact/social configuration lives in database records, not
Python source. Local configured records are not transferred by Git push:

- Run/review configure_primary_navigation (preview default, --apply adds missing
  records) and configure_footer_directory in production only after reconciliation.
  These commands never import local users/orders/payments or replace products.
- Configure the approved public email labibf2580@gmail.com, support phone
  01300972969, WhatsApp URL https://wa.me/8801300972960, Facebook URL
  https://www.facebook.com/farhan.labib.888684 and GitHub URL
  https://github.com/Farhan2580 through Admin. Preserve any newer production values.
- Upload the owner's original support portrait through Business Links using
  persistent storage. No personal uploaded files, local database, credentials,
  environment files, virtual environments, browser fixtures or IDE settings are
  part of this source change.
- Configure approved collection banners/content and genuine Apple collection
  placements through Admin; never invent product records or overwrite prices.

Run production checks and read-only live page/media verification after the
operator's deploy. Keep online payment methods disabled or sandbox-only until
merchant setup and separate live-payment authorization are complete.

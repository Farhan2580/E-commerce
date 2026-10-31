Phones and Tablets use separate catalog categories in Django Admin and the storefront.
Choose **Phones** for mobile phones and **Tablets** for iPads and other tablets when
adding or editing a product. Each storefront menu shows only its category and children.

Migration `0022_separate_phones_and_tablets` keeps the old combined category ID for
Phones, merges an existing Phones category into it, and reconnects navigation,
home sections, coupons and footer links. Explicit tablet product names or a
Tablet device type move to Tablets; other products keep the original category ID.
Product IDs, uploads, variants and order records are preserved. Promotions that
covered the combined category continue to cover both categories.

For deployment, back up the database, then run `python manage.py migrate` using
the deployment's configured interpreter. The data migration cannot be reversed
automatically; restore the backup to undo the category merge.

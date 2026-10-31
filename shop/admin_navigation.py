"""Shared Admin directory. Entries use Django's permission-filtered model list."""
SECTIONS = (
    ('catalog', 'Catalog', 'Products, categories and verified product information.', (
        ('shop.Product', 'Products', 'Prices, stock, options, photos and specifications.'),
        ('shop.Category', 'Categories', 'Organize Phones, Tablets and other collections.'),
        ('shop.Brand', 'Brands', 'Brand names, logos and storefront order.'),
        ('shop.ProductWarranty', 'Product warranties', 'Verified coverage, duration and claim instructions.'),
        ('shop.ProductPurpose', 'Gadget Finder rules', 'Verified recommendations for gaming, camera, study and work.'),
        ('shop.Compatibility', 'Accessory compatibility', 'Verified device pairings and bought-together suggestions.'),
        ('shop.PCComponent', 'PC components', 'Specifications used by the PC Builder.'),
    )),
    ('orders', 'Orders & delivery', 'Fulfillment, preorders and delivery areas.', (
        ('shop.Order', 'Orders', 'Customer orders, fulfillment, tracking and payment records.'),
        ('shop.Preorder', 'Preorders', 'Arrival estimates, advance status and customer updates.'),
        ('shop.DeliveryZone', 'Delivery areas', 'Delivery charges and business-day estimates.'),
    )),
    ('payments', 'Payments & promotions', 'Receipt review, completed refunds and discounts.', (
        ('shop.ManualPaymentClaim', 'Manual payment review', 'Review bKash references against merchant receipts.'),
        ('shop.RefundRecord', 'Completed refunds', 'Record actual completed refunds and their references.'),
        ('shop.Coupon', 'Coupons', 'Discount rules, dates and eligible customers or products.'),
    )),
    ('support', 'Customer support', 'Requests, reviews, questions and subscriptions.', (
        ('shop.ServiceClaim', 'Returns & warranty requests', 'Review item-specific requests and publish progress updates.'),
        ('shop.SupportRequest', 'Support inbox', 'Customer enquiries and assigned support work.'),
        ('shop.ProductQuestion', 'Product questions', 'Answer and publish customer questions.'),
        ('shop.Review', 'Customer reviews', 'Ratings, comments and customer product photos.'),
        ('shop.StockAlert', 'Stock subscriptions', 'Restock subscriptions and email delivery status.'),
        ('shop.PriceAlert', 'Price subscriptions', 'Target prices, selected options and notification status.'),
    )),
    ('storefront', 'Storefront & content', 'Everything customers see on the website.', (
        ('shop.NavigationItem', 'Main navigation', 'Connect each menu label to its category or brand.'),
        ('shop.Banner', 'Homepage banners', 'Hero images, headlines and destination links.'),
        ('shop.HomeSection', 'Homepage collections', 'Curate product sections and their display order.'),
        ('shop.Offer', 'Offer pages', 'Promotional cards and linked catalog products.'),
        ('shop.FooterGroup', 'Footer directory', 'Footer category, brand and collection links.'),
        ('shop.InformationPage', 'Information & policies', 'Publish shipping, returns, warranty and business pages.'),
        ('shop.FAQ', 'FAQs', 'Published questions and approved answers.'),
    )),
    ('settings', 'Store settings', 'Store identity, verified contacts and checkout configuration.', (
        ('shop.StoreSettings', 'Store configuration', 'Store details, payment settings and verified contact information.'),
        ('shop.BusinessLink', 'Contact & social links', 'Verified WhatsApp, social profiles and map links.'),
        ('shop.Outlet', 'Store outlets', 'Verified addresses, opening hours and map links.'),
    )),
    ('access', 'People & access', 'Staff accounts, customer accounts and permissions.', (
        ('auth.User', 'Users', 'Customer and staff accounts with assigned access.'),
        ('auth.Group', 'Permission groups', 'Manage staff roles with Django permissions.'),
    )),
    ('records', 'History & records', 'Audit trails and supporting customer records.', (
        ('shop.CatalogActivity', 'Price, stock & status activity', 'Who changed a value, what changed and its source.'),
        ('shop.OrderItem', 'Purchased items', 'Read-only item, quantity and price snapshots from orders.'),
        ('shop.CouponRedemption', 'Coupon usage', 'Discount redemptions linked to customers and orders.'),
        ('shop.Wishlist', 'Saved products', 'Customer wishlist records.'),
        ('shop.SavedAddress', 'Saved addresses', 'Customer address book records.'),
    )),
)


def grouped_navigation(app_list, request_path=''):
    available = {f'{app["app_label"]}.{model["object_name"]}': model
                 for app in app_list for model in app['models']}
    groups = []
    for key, title, description, entries in SECTIONS:
        models = []
        for label, name, help_text in entries:
            model = available.pop(label, None)
            if model is not None:
                model = {**model, 'name': name, 'description': help_text}
                model['url'] = model.get('admin_url') or model.get('add_url')
                model['current'] = bool(model.get('admin_url') and request_path.startswith(model['admin_url']))
                models.append(model)
        if models:
            groups.append({'key': key, 'title': title, 'description': description, 'models': models})
    if available:
        models = [{**model, 'url': model.get('admin_url') or model.get('add_url'),
                   'description': 'Additional registered administration tool.'} for model in available.values()]
        groups.append({'key': 'other', 'title': 'Other tools', 'description': 'Additional registered tools.', 'models': models})
    return groups

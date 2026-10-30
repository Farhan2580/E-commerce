"""Public information, localization and abuse controls; no payment credentials."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import BusinessLink, InformationPage, ProductWarranty, SupportRateLimit, validate_public_https
from .services import enabled_payment_methods, settings_for_store

OPERATIONAL_PAGES = {'contact', 'tracking', 'faqs', 'payments'}
UI = {
    'en': {
        'care': 'Customer Care', 'policies': 'Policies', 'company': 'Company / Account', 'language': 'Information language',
        'home': 'Home', 'updated': 'Last updated', 'preview': 'Staff preview — this draft is not public.',
        'fallback': 'Some content is shown in English because a Bangla translation is not yet available.',
        'contact_intro': 'Get in touch with GadgetFlow using the verified details below, or send a message to store staff.',
        'phone': 'Phone', 'email': 'Email', 'address': 'Address', 'hours': 'Support hours', 'license': 'Business registration details',
        'name': 'Name', 'message': 'Message', 'send': 'Send message', 'contact_form': 'Send us a message',
        'received': 'Your message has been saved for store staff. Reference:', 'form_error': 'Please correct the highlighted fields.',
        'rate_error': 'Too many support submissions. Please try again later or use the verified contact details.',
        'storage_error': 'Support is temporarily busy. Your message was not confirmed; please retry this same form.',
        'search': 'Search FAQs', 'search_action': 'Search', 'all_groups': 'All topics', 'no_faqs': 'No published answers match your search.',
        'tracking_intro': 'Track orders from your signed-in account. Order numbers or phone numbers alone cannot unlock order details.',
        'choose_order': 'Choose your order', 'track': 'Track order', 'no_orders': 'There are no orders in this account yet.',
        'order': 'Order', 'status': 'Order progress', 'placed': 'Placed', 'courier': 'Courier', 'tracking_number': 'Tracking number',
        'tracking_link': 'Open courier tracking', 'not_assigned': 'Courier tracking has not been assigned to this order.',
        'no_events': 'Detailed fulfillment events were not recorded for this historical order.', 'order_support': 'Ask about this order',
        'order_details': 'Full order details', 'support_contact': 'Contact support', 'shipping_charge': 'Current flat shipping charge per nonempty order',
        'shipping_note': 'The checkout shipping setting is the source of this amount. Confirm delivery coverage and timing with support or the published delivery policy.',
        'enabled_payments': 'Enabled payment methods', 'cod': 'Cash on Delivery', 'cod_help': 'Select Cash on Delivery at checkout when it is enabled.',
        'bkash': 'bKash — manual transfer', 'bkash_help': 'Use the receiving number below. Checkout requires your sender number and transaction reference. Transfers remain under manual review until staff verify payment.',
        'receiving_number': 'Public receiving number', 'no_payments': 'No payment methods are currently enabled.',
        'payment_help': 'An order confirmation does not mean a payment has been verified. If checkout reports an error, review your cart and retry the same checkout form. For transfer questions, contact support with your order reference. Never share passwords or one-time codes.',
        'cookies': 'Cookies and browser storage in this implementation', 'essential': 'Required first-party cookies', 'local_storage': 'Functional local storage',
        'no_analytics': 'No analytics or marketing scripts are included in the current active storefront. There are no optional tracking scripts to enable or withdraw.',
        'font_provider': 'The storefront loads Google Fonts from fonts.googleapis.com and fonts.gstatic.com. These font requests are separate from analytics.',
        'map_note': 'Maps, messaging and social profiles open only when you follow their links; no third-party map is embedded here.',
        'warranty': 'Product warranty', 'period': 'Period', 'coverage': 'Coverage', 'exclusions': 'Exclusions', 'claim_steps': 'How to make a claim',
        'service_contact': 'Verified service contact', 'find_warranty': 'Find a product warranty', 'no_warranty': 'No verified product warranty terms match this search.',
        'categories': 'Browse our current product categories', 'contact_topic': 'Topic', 'general': 'General enquiry', 'warranty_topic': 'Warranty enquiry',
        'account': 'Account details', 'orders': 'Order history', 'wishlist': 'Your wishlist', 'cart': 'Shopping cart', 'catalog': 'All products', 'offers': 'Offers & deals', 'preorder': 'Request a preorder',
        'tracking_faq': 'Sign in and choose one of your orders on Track Your Order. The page shows recorded fulfillment events and courier tracking when staff have assigned it.',
        'support_faq': 'Use Contact Us to view verified contact details or send a message to store staff.',
    },
    'bn': {
        'care': 'গ্রাহক সেবা', 'policies': 'নীতিমালা', 'company': 'প্রতিষ্ঠান / অ্যাকাউন্ট', 'language': 'তথ্যের ভাষা',
        'home': 'হোম', 'updated': 'সর্বশেষ হালনাগাদ', 'preview': 'কর্মীদের প্রিভিউ — এই খসড়া প্রকাশিত নয়।',
        'fallback': 'বাংলা অনুবাদ এখনো না থাকায় কিছু তথ্য ইংরেজিতে দেখানো হচ্ছে।',
        'contact_intro': 'নিচের যাচাইকৃত যোগাযোগের তথ্য ব্যবহার করুন অথবা GadgetFlow-এর কর্মীদের একটি বার্তা পাঠান।',
        'phone': 'ফোন', 'email': 'ইমেইল', 'address': 'ঠিকানা', 'hours': 'সহায়তার সময়', 'license': 'ব্যবসার নিবন্ধনের তথ্য',
        'name': 'নাম', 'message': 'বার্তা', 'send': 'বার্তা পাঠান', 'contact_form': 'আমাদের বার্তা পাঠান',
        'received': 'আপনার বার্তা কর্মীদের জন্য সংরক্ষিত হয়েছে। রেফারেন্স:', 'form_error': 'চিহ্নিত ঘরগুলোর তথ্য সংশোধন করুন।',
        'rate_error': 'অল্প সময়ে অনেক বার্তা পাঠানো হয়েছে। পরে চেষ্টা করুন অথবা যাচাইকৃত যোগাযোগের তথ্য ব্যবহার করুন।',
        'storage_error': 'সহায়তা সেবা সাময়িক ব্যস্ত। বার্তা সংরক্ষণের নিশ্চয়তা মেলেনি; একই ফর্ম দিয়ে আবার চেষ্টা করুন।',
        'search': 'প্রশ্নোত্তর খুঁজুন', 'search_action': 'খুঁজুন', 'all_groups': 'সব বিষয়', 'no_faqs': 'আপনার অনুসন্ধানের সঙ্গে মিলে এমন প্রকাশিত উত্তর নেই।',
        'tracking_intro': 'নিজের অ্যাকাউন্টে প্রবেশ করে অর্ডার দেখুন। শুধু অর্ডার নম্বর বা ফোন নম্বর দিয়ে অর্ডারের তথ্য দেখা যায় না।',
        'choose_order': 'আপনার অর্ডার বেছে নিন', 'track': 'অর্ডার ট্র্যাক করুন', 'no_orders': 'এই অ্যাকাউন্টে এখনো কোনো অর্ডার নেই।',
        'order': 'অর্ডার', 'status': 'অর্ডারের অগ্রগতি', 'placed': 'অর্ডারের তারিখ', 'courier': 'কুরিয়ার', 'tracking_number': 'ট্র্যাকিং নম্বর',
        'tracking_link': 'কুরিয়ারের ট্র্যাকিং খুলুন', 'not_assigned': 'এই অর্ডারের কুরিয়ার ট্র্যাকিং এখনো যুক্ত করা হয়নি।',
        'no_events': 'এই পুরোনো অর্ডারের বিস্তারিত অগ্রগতির ইতিহাস সংরক্ষিত নেই।', 'order_support': 'এই অর্ডার সম্পর্কে সাহায্য চান',
        'order_details': 'অর্ডারের পূর্ণ বিবরণ', 'support_contact': 'সহায়তার জন্য যোগাযোগ', 'shipping_charge': 'পণ্য থাকা প্রতিটি অর্ডারের বর্তমান নির্ধারিত ডেলিভারি চার্জ',
        'shipping_note': 'এই পরিমাণ চেকআউটের ডেলিভারি সেটিং থেকে দেখানো হচ্ছে। সহায়তা বিভাগ বা প্রকাশিত ডেলিভারি নীতি থেকে এলাকা ও সময় নিশ্চিত করুন।',
        'enabled_payments': 'চালু পেমেন্ট পদ্ধতি', 'cod': 'ক্যাশ অন ডেলিভারি', 'cod_help': 'চালু থাকলে চেকআউটে ক্যাশ অন ডেলিভারি বেছে নিন।',
        'bkash': 'বিকাশ — ম্যানুয়াল ট্রান্সফার', 'bkash_help': 'নিচের গ্রহণকারী নম্বর ব্যবহার করুন। চেকআউটে প্রেরকের নম্বর ও লেনদেনের রেফারেন্স দিতে হবে। কর্মীরা যাচাই না করা পর্যন্ত পেমেন্ট ম্যানুয়াল রিভিউতে থাকবে।',
        'receiving_number': 'পেমেন্ট গ্রহণকারী নম্বর', 'no_payments': 'বর্তমানে কোনো পেমেন্ট পদ্ধতি চালু নেই।',
        'payment_help': 'অর্ডারের নিশ্চয়তা মানে পেমেন্ট যাচাই হয়েছে এমন নয়। চেকআউটে সমস্যা দেখালে কার্ট পরীক্ষা করে একই ফর্ম দিয়ে আবার চেষ্টা করুন। ট্রান্সফার সম্পর্কে জানতে অর্ডারের রেফারেন্সসহ যোগাযোগ করুন। পাসওয়ার্ড বা একবার ব্যবহারযোগ্য কোড কাউকে দেবেন না।',
        'cookies': 'এই সাইটের কুকি ও ব্রাউজার স্টোরেজ', 'essential': 'প্রয়োজনীয় নিজস্ব কুকি', 'local_storage': 'কার্যকরী লোকাল স্টোরেজ',
        'no_analytics': 'বর্তমান সক্রিয় স্টোরে অ্যানালিটিক্স বা মার্কেটিং স্ক্রিপ্ট নেই। চালু বা বন্ধ করার মতো ঐচ্ছিক ট্র্যাকিং স্ক্রিপ্ট নেই।',
        'font_provider': 'স্টোরে fonts.googleapis.com ও fonts.gstatic.com থেকে Google Fonts লোড হয়। এই ফন্টের অনুরোধ অ্যানালিটিক্স নয়।',
        'map_note': 'লিংকে ক্লিক করলেই কেবল মানচিত্র, মেসেজিং বা সামাজিক প্রোফাইল খোলে; এখানে কোনো তৃতীয় পক্ষের মানচিত্র এমবেড করা নেই।',
        'warranty': 'পণ্যের ওয়ারেন্টি', 'period': 'মেয়াদ', 'coverage': 'যা অন্তর্ভুক্ত', 'exclusions': 'যা অন্তর্ভুক্ত নয়', 'claim_steps': 'দাবি করার পদ্ধতি',
        'service_contact': 'যাচাইকৃত সেবা যোগাযোগ', 'find_warranty': 'পণ্যের ওয়ারেন্টি খুঁজুন', 'no_warranty': 'এই অনুসন্ধানে যাচাইকৃত পণ্যের ওয়ারেন্টির তথ্য নেই।',
        'categories': 'বর্তমান পণ্যের বিভাগ দেখুন', 'contact_topic': 'বিষয়', 'general': 'সাধারণ জিজ্ঞাসা', 'warranty_topic': 'ওয়ারেন্টি সম্পর্কে জিজ্ঞাসা',
        'account': 'অ্যাকাউন্টের তথ্য', 'orders': 'অর্ডারের ইতিহাস', 'wishlist': 'আপনার উইশলিস্ট', 'cart': 'শপিং কার্ট', 'catalog': 'সব পণ্য', 'offers': 'অফার', 'preorder': 'প্রি-অর্ডারের অনুরোধ',
        'tracking_faq': 'অ্যাকাউন্টে প্রবেশ করে অর্ডার ট্র্যাকিং পাতায় নিজের অর্ডার বেছে নিন। সংরক্ষিত অগ্রগতি এবং কর্মীরা যুক্ত করলে কুরিয়ারের ট্র্যাকিং দেখা যাবে।',
        'support_faq': 'যাচাইকৃত যোগাযোগের তথ্য দেখতে অথবা কর্মীদের বার্তা পাঠাতে যোগাযোগ পাতায় যান।',
    },
}


def language_for(request):
    # Ignore legacy selections and normalize them without removing session data.
    if request.session.get('support_language') not in (None, 'en'):
        request.session['support_language'] = 'en'
    return 'en'


def text(en, bn, language):
    # Translation fields remain available to staff; customer content is English.
    return en or ''


def localized(obj, field, language):
    return text(getattr(obj, field + '_en', ''), getattr(obj, field + '_bn', ''), language)


def page_is_public(page):
    return page.status == 'published' and (page.slug in OPERATIONAL_PAGES or page.body_en.strip() or page.body_bn.strip() or any(section.body_en.strip() or section.body_bn.strip() for section in page.sections.all()))


def public_store(store, language):
    return SimpleNamespace(name=store.name, tagline=store.tagline,
                           phone=store.phone if store.phone_verified else '', email=store.email if store.email_verified else '',
                           address=text(store.address, store.address_bn, language) if store.address_verified else '',
                           support_hours=localized(store, 'support_hours', language),
                           license_details=localized(store, 'license_details', language) if store.license_verified else '',
                           shipping_price=store.shipping_price, bkash_number=store.bkash_number if store.manual_bkash_ready else '',
                           cod_enabled=store.cod_enabled, updated_at=store.updated_at)


def support_context(request, store=None):
    store = store or settings_for_store()
    language = language_for(request)
    footer = {'care': [], 'policies': [], 'company': []}
    public_slugs = set()
    for page in InformationPage.objects.filter(status='published').prefetch_related('sections'):
        if page_is_public(page):
            public_slugs.add(page.slug)
            url = reverse('track_order') if page.slug == 'tracking' else reverse('policy', args=[page.slug])
            footer[page.footer_group].append({'title': localized(page, 'title', language), 'url': url})
    labels = dict(InformationPage.SLUGS)
    labels.update(shipping='Shipping Policy', returns='Returns & Refund Policy', warranty='Warranty Policy')
    def links(slugs):
        return [{'title': labels[slug], 'url': reverse('track_order') if slug == 'tracking'
                 else reverse('policy', args=[slug])} for slug in slugs if slug in public_slugs]
    footer['care'] = links(['contact', 'tracking', 'faqs', 'payments', 'shipping', 'returns', 'warranty'])
    footer['company'] = links(['about', 'terms', 'privacy', 'cookies'])
    return {'store': public_store(store, language), 'support_language': language, 'support_ui': UI[language],
            'information_footer': footer, 'information_public_slugs': public_slugs,
            'footer_social_links': [link for link in business_links('en') if link['kind'] == 'social' and link['label']],
            'footer_payment_badges': footer_payment_badges(store)}


def footer_payment_badges(store):
    from .payments import accepted_card_brands
    methods = dict(enabled_payment_methods(store))
    badges = []
    if 'COD' in methods:
        badges.append({'name': 'Cash on Delivery', 'short': 'COD'})
    if 'BKASH' in methods:
        badges.append({'name': 'bKash', 'asset': 'shop/payment-brands/bkash.png'})
    if 'ONLINE_BKASH' in methods:
        badges.append({'name': 'bKash', 'asset': 'shop/payment-brands/bkash.png', 'test_only': True})
    if 'CARD' in methods:
        badges.extend({**brand, 'test_only': True} for brand in accepted_card_brands())
    return badges


def business_links(language):
    links = []
    for link in BusinessLink.objects.filter(is_verified=True):
        try:
            validate_public_https(link.url)
        except ValidationError:
            continue
        links.append({'label': localized(link, 'label', language), 'url': link.url, 'kind': link.kind, 'updated_at': link.updated_at})
    return links


def page_content(page, language):
    language = 'en'
    sections = []
    updated = page.updated_at
    for section in page.sections.all():
        if not section.body_en.strip():
            continue
        sections.append({'heading': localized(section, 'heading', language), 'body': localized(section, 'body', language),
                         'language': language})
        updated = max(updated, section.updated_at)
    body = localized(page, 'body', language)
    if not body.strip() and page.body_bn.strip():
        body = 'English content is not available yet. Please contact the store for details.'
    return {'page': page, 'title': localized(page, 'title', language), 'page_body': body,
            'information_sections': sections, 'translation_fallback': False, 'last_updated': updated,
            'document_language': language}


def payment_cards(store, language):
    ui = UI['en']
    return [{'code': code, 'title': ui['cod'] if code == 'COD' else ('Card' if code == 'CARD' else ui['bkash']),
             'instructions': ui['cod_help'] if code == 'COD' else (store.bkash_manual_instructions if code == 'BKASH' else 'Pay securely on the provider’s checkout page.'),
             'number': store.bkash_number if code == 'BKASH' else ''} for code, _ in enabled_payment_methods(store)]


def faq_answer(faq, store, language):
    language = 'en'
    ui = UI[language]
    if faq.answer_source == 'payments':
        cards = payment_cards(store, language)
        return '\n\n'.join(card['title'] + ': ' + card['instructions'] for card in cards) or ui['no_payments']
    if faq.answer_source == 'shipping':
        return f'{ui["shipping_charge"]}: ৳{store.shipping_price:.2f}. {ui["shipping_note"]}'
    if faq.answer_source == 'tracking':
        return ui['tracking_faq']
    if faq.answer_source == 'support':
        return ui['support_faq']
    return localized(faq, 'answer', language)


def warranty_content(warranty, language):
    language = 'en'
    types = {'manufacturer': ('Manufacturer', 'প্রস্তুতকারকের'), 'seller': ('Seller', 'বিক্রেতার'),
             'service': ('Service', 'সার্ভিস'), 'none': ('No warranty', 'ওয়ারেন্টি নেই')}
    return {'product': warranty.product, 'type': types[warranty.warranty_type][language == 'bn'],
            **{field: localized(warranty, field, language) for field in ['period', 'coverage', 'exclusions', 'claim_steps', 'service_address']},
            'phone': warranty.service_phone, 'email': warranty.service_email, 'updated_at': warranty.updated_at}


def form_nonce(request):
    if not request.session.get('support_nonce'):
        request.session['support_nonce'] = uuid4().hex
    return request.session['support_nonce']


def support_token(request, scope='contact'):
    return signing.dumps({'nonce': form_nonce(request), 'scope': scope, 'token': str(uuid4())}, salt='shop.support.form')


@transaction.atomic
def allow_submission(request):
    """Shared DB rate limit, not a per-worker cache. Never trust forwarded IP headers."""
    now = timezone.now()
    bucket = int(now.timestamp()) // 3600
    subjects = [('ip:' + request.META.get('REMOTE_ADDR', 'unknown'), 5)]
    if request.user.is_authenticated:
        subjects.append(('user:' + str(request.user.pk), 10))
    rows = []
    for subject, limit in subjects:
        key = salted_hmac('shop.support.rate', f'{subject}:{bucket}').hexdigest()
        row, _ = SupportRateLimit.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(hours=2)})
        if row.count >= limit:
            return False
        rows.append((row, limit))
    for row, limit in rows:
        if not SupportRateLimit.objects.filter(pk=row.pk, count__lt=limit).update(count=F('count') + 1):
            transaction.set_rollback(True)
            return False
    return True

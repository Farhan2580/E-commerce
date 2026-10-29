"""Factual operational pages plus private policy outlines; no invented business terms."""
from django.db import migrations


PAGES = [
    ('contact', 'Contact Us', 'যোগাযোগ', 'care'),
    ('tracking', 'Track Your Order', 'অর্ডার ট্র্যাক করুন', 'care'),
    ('faqs', 'FAQs', 'প্রশ্নোত্তর', 'care'),
    ('payments', 'Payment Methods', 'পেমেন্ট পদ্ধতি', 'care'),
    ('shipping', 'Shipping & Delivery', 'শিপিং ও ডেলিভারি', 'policies'),
    ('returns', 'Returns & Refunds', 'রিটার্ন ও রিফান্ড', 'policies'),
    ('warranty', 'Warranty & Exchange', 'ওয়ারেন্টি ও এক্সচেঞ্জ', 'policies'),
    ('terms', 'Terms & Conditions', 'শর্তাবলি', 'policies'),
    ('privacy', 'Privacy Policy', 'গোপনীয়তা নীতি', 'policies'),
    ('cookies', 'Cookie Policy', 'কুকি নীতি', 'policies'),
    ('about', 'About Us', 'আমাদের সম্পর্কে', 'company'),
]

OUTLINES = {
    'contact': [('Support hours', 'সহায়তার সময়'), ('How to reach us', 'যোগাযোগের উপায়')],
    'tracking': [('Order support', 'অর্ডার সংক্রান্ত সহায়তা')],
    'faqs': [],
    'payments': [('COD conditions', 'ক্যাশ অন ডেলিভারির শর্ত'), ('Manual transfer instructions', 'ম্যানুয়াল ট্রান্সফারের নির্দেশনা'), ('Payment-failure help', 'পেমেন্ট সমস্যায় করণীয়')],
    'shipping': [('Delivery areas', 'ডেলিভারির এলাকা'), ('Processing times', 'অর্ডার প্রস্তুতের সময়'), ('Estimated delivery times', 'আনুমানিক ডেলিভারির সময়'), ('Charges', 'ডেলিভারি চার্জ'), ('Free-delivery conditions', 'বিনামূল্যে ডেলিভারির শর্ত'), ('Courier partners', 'কুরিয়ার প্রতিষ্ঠান'), ('Delays', 'দেরি হলে করণীয়'), ('Parcel inspection', 'পার্সেল পরীক্ষা'), ('Failed delivery', 'ডেলিভারি ব্যর্থ হলে করণীয়')],
    'returns': [('Eligibility and time limits', 'যোগ্যতা ও সময়সীমা'), ('Electronics exclusions', 'ইলেকট্রনিকস পণ্যের ব্যতিক্রম'), ('Packaging and accessories', 'মোড়ক ও আনুষঙ্গিক সামগ্রী'), ('Return steps', 'রিটার্নের ধাপ'), ('Wrong or damaged items', 'ভুল বা ক্ষতিগ্রস্ত পণ্য'), ('Return shipping costs', 'রিটার্নের পরিবহন খরচ'), ('Refund methods and timing', 'রিফান্ডের মাধ্যম ও সময়'), ('Exchange rules', 'এক্সচেঞ্জের নিয়ম')],
    'terms': [('Website use', 'ওয়েবসাইটের ব্যবহার'), ('Account responsibility', 'অ্যাকাউন্টের দায়িত্ব'), ('Pricing errors', 'মূল্যের ভুল'), ('Order acceptance and cancellation', 'অর্ডার গ্রহণ ও বাতিল'), ('Payments', 'পেমেন্ট'), ('Intellectual property', 'মেধাস্বত্ব'), ('Liability', 'দায়বদ্ধতা'), ('Updates', 'পরিবর্তন'), ('Jurisdiction', 'প্রযোজ্য বিচারব্যবস্থা'), ('Contact details', 'যোগাযোগের তথ্য')],
    'privacy': [('Data collected', 'সংগৃহীত তথ্য'), ('Purposes', 'ব্যবহারের উদ্দেশ্য'), ('Service providers', 'সেবা প্রদানকারী'), ('Cookies and browser storage', 'কুকি ও ব্রাউজার স্টোরেজ'), ('Retention', 'তথ্য সংরক্ষণের সময়'), ('Security practices', 'নিরাপত্তার ব্যবস্থা'), ('Customer requests', 'গ্রাহকের অনুরোধ'), ('Third-party links', 'তৃতীয় পক্ষের লিংক'), ('Updates', 'পরিবর্তন'), ('Contact details', 'যোগাযোগের তথ্য')],
    'cookies': [('Required cookies', 'প্রয়োজনীয় কুকি'), ('Functional local storage', 'কার্যকরী লোকাল স্টোরেজ'), ('External font requests', 'বাহ্যিক ফন্টের অনুরোধ'), ('Optional tracking', 'ঐচ্ছিক ট্র্যাকিং')],
    'about': [('Brand story', 'প্রতিষ্ঠানের গল্প'), ('Mission', 'লক্ষ্য'), ('Product categories', 'পণ্যের বিভাগ'), ('Founder and team', 'প্রতিষ্ঠাতা ও দল'), ('Verified business details', 'যাচাইকৃত ব্যবসার তথ্য')],
    'warranty': [('Warranty types and periods', 'ওয়ারেন্টির ধরন ও মেয়াদ'), ('Coverage', 'অন্তর্ভুক্ত সেবা'), ('Exclusions', 'ব্যতিক্রম'), ('Claim steps', 'দাবি করার ধাপ'), ('Verified service contacts', 'যাচাইকৃত সেবা যোগাযোগ'), ('Exchange rules', 'এক্সচেঞ্জের নিয়ম')],
}

NOTES = {
    'contact': 'Confirm support hours, support email, verified address, WhatsApp/Messenger URLs, map/social profiles and any registration details. A phone number does not prove WhatsApp is enabled.',
    'tracking': 'Assign courier fields through each existing Order. No guest tracking exists; keep authentication and ownership checks.',
    'faqs': 'Publish only verified answers. Unknown delivery times, cancellations, returns and authenticity assurances remain draft FAQs.',
    'payments': 'Live methods come from Store settings. Confirm COD areas/conditions and transfer instructions; do not add unsupported gateway brands or promise automatic payment success.',
    'shipping': 'Specify delivery areas, processing/estimated times, courier partners, delays, parcel inspection and failed-delivery procedures. Charges come from the checkout shipping_price field. There is currently no conditional free-delivery threshold in checkout; do not publish a threshold until checkout implements the same rule.',
    'returns': 'Business decision required: eligibility, deadlines, opened/activated electronics, consumables/software, packaging/accessories, wrong/damaged goods, evidence, return process/cost payer, refund methods/times, and exchange eligibility. Review before publishing.',
    'terms': 'UNPUBLISHED EDITORIAL OUTLINE ONLY. Owner/legal reviewer must supply and approve actual terms for every section, including jurisdiction. No legally binding clauses or compliance claims have been generated.',
    'privacy': 'Review the inspected implementation facts below. Confirm hosting/SMTP/courier/payment providers, retention periods, support-rate hash cleanup, user request procedure, actual production security/cookie configuration, and update/contact terms. Passwords are hashed; no encryption-at-rest or legal-compliance guarantee is claimed.',
    'cookies': 'Review the runtime cookie/storage inventory before publishing. Current active base/storefront scripts contain no optional analytics/marketing. Google Fonts is an external font resource. If optional trackers are added later, implement consent gating/withdrawal before loading them.',
    'about': 'Owner must supply the real brand story, mission, founder/team and registration details. Product categories are read from the actual catalog. No founding date, authenticity claim or business license was invented.',
    'warranty': 'Enter verified per-product type, period, coverage, exclusions, claim steps and service contacts through Product warranties or the Product inline. Confirm general exchange rules; never infer warranties from product marketing.',
}

PRIVACY_FACTS = {
    'Data collected': (
        'The implementation stores account usernames, password hashes and account dates; checkout names, email addresses, phone numbers, delivery addresses, purchased items and order/payment status; optional manual-transfer sender numbers and transaction references; saved addresses, wishlists, reviews, preorders (including uploaded images), coupon redemptions and stock-alert email subscriptions. Support forms store the submitted name, phone, email, message, topic, preferred information language, timestamps and an optional authenticated account/order association. Browsing history, cart and comparison selections are kept in the Django session. Support rate controls store keyed hashes and counters, not raw IP addresses.',
        'এখানে অ্যাকাউন্টের নাম, পাসওয়ার্ডের হ্যাশ ও তারিখ; চেকআউটের নাম, ইমেইল, ফোন, ঠিকানা, কেনা পণ্য ও অর্ডার/পেমেন্টের অবস্থা; ম্যানুয়াল ট্রান্সফারের প্রেরক নম্বর ও রেফারেন্স; সংরক্ষিত ঠিকানা, উইশলিস্ট, রিভিউ, ছবিসহ প্রি-অর্ডার, কুপন ব্যবহার এবং স্টক-অ্যালার্টের ইমেইল সংরক্ষিত হয়। সহায়তা ফর্মের নাম, ফোন, ইমেইল, বার্তা, বিষয়, তথ্যের ভাষা, সময় ও প্রযোজ্য অ্যাকাউন্ট/অর্ডারের সংযোগ সংরক্ষিত হয়। কার্ট, তুলনা ও দেখার ইতিহাস Django সেশনে থাকে। রেট নিয়ন্ত্রণে আসল আইপি নয়, কীযুক্ত হ্যাশ ও কাউন্টার রাখা হয়।'),
    'Purposes': (
        'These features support sign-in, cart/checkout, stock validation, order records, saved customer choices, customer-written reviews, preorder requests, coupon limits, requested stock emails and staff handling of support enquiries.',
        'এই তথ্য সাইন-ইন, কার্ট/চেকআউট, স্টক যাচাই, অর্ডারের রেকর্ড, গ্রাহকের সংরক্ষিত পছন্দ, রিভিউ, প্রি-অর্ডার, কুপনের সীমা, চাওয়া স্টক ইমেইল এবং কর্মীদের সহায়তা পরিচালনায় ব্যবহৃত হয়।'),
    'Service providers': (
        'The current project uses Django and a local SQLite database. Google Fonts is requested from fonts.googleapis.com and fonts.gstatic.com. Stock-alert email uses the configured SMTP provider when configured; the provider identity is not specified in this project. Contact forms save to Admin and do not send email automatically. This site records manual bKash submissions but does not execute an online gateway payment. Courier links are assigned by staff, not queried through an integrated courier API.',
        'বর্তমান প্রকল্পে Django ও স্থানীয় SQLite ডেটাবেস ব্যবহৃত হয়। Google Fonts fonts.googleapis.com ও fonts.gstatic.com থেকে আসে। স্টক-অ্যালার্টের ইমেইল কনফিগার করা SMTP সেবা ব্যবহার করে; প্রকল্পে সেবাদাতার পরিচয় নির্দিষ্ট করা নেই। যোগাযোগ ফর্মের বার্তা অ্যাডমিনে সংরক্ষিত হয়, স্বয়ংক্রিয় ইমেইল যায় না। সাইটে ম্যানুয়াল বিকাশের তথ্য সংরক্ষিত হয়, অনলাইন গেটওয়ে পেমেন্ট চালানো হয় না। কুরিয়ারের লিংক কর্মীরা যুক্ত করেন; কুরিয়ার API ব্যবহার করা হয় না।'),
    'Cookies and browser storage': (
        'Django session and CSRF cookies support account/cart state and form protection. Functional local storage retains the chosen theme and broadcasts shopping changes between tabs. The active storefront contains no analytics or marketing scripts.',
        'Django সেশন ও CSRF কুকি অ্যাকাউন্ট/কার্ট এবং ফর্মের সুরক্ষায় ব্যবহৃত হয়। লোকাল স্টোরেজে নির্বাচিত থিম ও ট্যাবের মধ্যে শপিং পরিবর্তনের সংকেত থাকে। সক্রিয় স্টোরে অ্যানালিটিক্স বা মার্কেটিং স্ক্রিপ্ট নেই।'),
    'Security practices': (
        'The application uses Django password hashing, CSRF-protected POST forms, authenticated ownership checks for orders and saved customer records, signed support-form tokens, honeypot/rate controls and transactional checkout. These describe implemented controls, not a guarantee against every security risk.',
        'অ্যাপে Django পাসওয়ার্ড হ্যাশিং, CSRF-সুরক্ষিত POST ফর্ম, অর্ডার ও গ্রাহকের রেকর্ডে মালিকানা যাচাই, স্বাক্ষরিত সহায়তা ফর্ম টোকেন, হানিপট/রেট নিয়ন্ত্রণ এবং ট্রানজ্যাকশনভিত্তিক চেকআউট আছে। এগুলো বাস্তবায়িত ব্যবস্থা; সব ঝুঁকি থেকে নিরাপত্তার নিশ্চয়তা নয়।'),
    'Customer requests': (
        'Customers can submit a message using the verified Contact Us details or support form for staff review.',
        'গ্রাহক যাচাইকৃত যোগাযোগের তথ্য বা সহায়তা ফর্ম ব্যবহার করে কর্মীদের পর্যালোচনার জন্য বার্তা পাঠাতে পারেন।'),
    'Third-party links': (
        'Configured messaging, map, social and courier links open third-party sites only when followed. Maps are not embedded. Google Fonts requests occur as the storefront loads.',
        'কনফিগার করা মেসেজিং, মানচিত্র, সামাজিক ও কুরিয়ার লিংকে ক্লিক করলে তৃতীয় পক্ষের সাইট খোলে। মানচিত্র এমবেড করা নেই। স্টোর লোডের সময় Google Fonts-এর অনুরোধ যায়।'),
}


def seed(apps, schema_editor):
    Page = apps.get_model('shop', 'InformationPage')
    Section = apps.get_model('shop', 'InformationSection')
    FAQ = apps.get_model('shop', 'FAQ')
    Store = apps.get_model('shop', 'StoreSettings')
    store, _ = Store.objects.get_or_create(pk=1)
    if not store.phone or store.phone == '01300972969':
        store.phone = '01300972969'
        store.phone_verified = True
        store.save(update_fields=['phone', 'phone_verified', 'updated_at'])
    legacy = {'shipping': store.shipping_policy, 'returns': store.returns_policy, 'privacy': store.privacy_policy}
    for position, (slug, en, bn, group) in enumerate(PAGES):
        status = 'published' if slug in {'contact', 'tracking', 'faqs', 'payments'} or legacy.get(slug, '').strip() else 'draft'
        page, _ = Page.objects.get_or_create(slug=slug, defaults={'title_en': en, 'title_bn': bn, 'footer_group': group,
            'position': position, 'status': status, 'body_en': legacy.get(slug, ''), 'editorial_notes': NOTES[slug]})
        for index, (heading, heading_bn) in enumerate(OUTLINES[slug]):
            en_body, bn_body = PRIVACY_FACTS.get(heading, ('', '')) if slug == 'privacy' else ('', '')
            Section.objects.get_or_create(page=page, heading_en=heading, defaults={'heading_bn': heading_bn, 'body_en': en_body, 'body_bn': bn_body, 'position': index})
        if slug == 'cookies' and not page.body_en:
            page.body_en = 'This page describes the cookies, functional browser storage and external font requests used by the current GadgetFlow implementation.'
            page.body_bn = 'এই পাতায় বর্তমান GadgetFlow-এর কুকি, কার্যকরী ব্রাউজার স্টোরেজ এবং বাহ্যিক ফন্টের অনুরোধের তথ্য রয়েছে।'
            page.save(update_fields=['body_en', 'body_bn'])
    facts = [
        ('ordering', 'How do I place an order?', 'কীভাবে অর্ডার করব?', 'text', 'Choose a product and any required option, add it to your cart, sign in, then complete delivery/payment details at checkout. Stock and totals are checked on the server.', 'পণ্য ও প্রয়োজনীয় অপশন বেছে কার্টে যোগ করুন, সাইন-ইন করুন এবং চেকআউটে ডেলিভারি ও পেমেন্টের তথ্য দিন। সার্ভারে স্টক ও মোট মূল্য যাচাই করা হয়।'),
        ('payments', 'Which payment methods are enabled?', 'কোন পেমেন্ট পদ্ধতি চালু আছে?', 'payments', '', ''),
        ('cod', 'Can I choose Cash on Delivery?', 'ক্যাশ অন ডেলিভারি বেছে নিতে পারব?', 'payments', '', ''),
        ('delivery', 'What is the current shipping charge?', 'বর্তমান ডেলিভারি চার্জ কত?', 'shipping', '', ''),
        ('tracking', 'How do I track my order?', 'অর্ডার কীভাবে ট্র্যাক করব?', 'tracking', '', ''),
        ('support', 'How can I contact support?', 'সহায়তার জন্য কীভাবে যোগাযোগ করব?', 'support', '', ''),
    ]
    for position, (group, en, bn, source, answer_en, answer_bn) in enumerate(facts):
        FAQ.objects.get_or_create(question_en=en, defaults={'question_bn': bn, 'group': group, 'answer_source': source,
            'answer_en': answer_en, 'answer_bn': answer_bn, 'status': 'published', 'position': position})
    unknown = [('delivery', 'How long does delivery take?', 'ডেলিভারিতে কত সময় লাগে?'), ('cancellation', 'How can I cancel an order?', 'অর্ডার কীভাবে বাতিল করব?'),
               ('returns', 'What are the return and refund rules?', 'রিটার্ন ও রিফান্ডের নিয়ম কী?'), ('authenticity', 'What authenticity assurances apply?', 'পণ্যের আসল হওয়ার বিষয়ে কী নিশ্চয়তা আছে?')]
    for group, en, bn in unknown:
        FAQ.objects.get_or_create(question_en=en, defaults={'question_bn': bn, 'group': group, 'status': 'draft', 'editorial_notes': 'Owner must supply and verify the actual business answer before publication.'})


class Migration(migrations.Migration):
    dependencies = [('shop', '0009_information_and_support')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

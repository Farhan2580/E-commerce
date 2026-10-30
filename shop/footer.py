"""Footer navigation from published records, with bounded prefetched queries."""
from urllib.parse import urlencode, urlsplit
from django.core.exceptions import ValidationError
from django.urls import reverse
from .models import FooterGroup, Outlet, validate_public_https
from .whatsapp import whatsapp_url


def public_outlets():
    result = []
    for outlet in Outlet.objects.filter(visible=True):
        try:
            validate_public_https(outlet.map_url)
        except ValidationError:
            continue
        if outlet.address.strip():
            result.append(outlet)
    return result


def footer_context(pages, business):
    support, policies = [], []
    for page in pages:
        item = {'title': page.title_en, 'url': reverse('track_order') if page.slug == 'tracking'
                else reverse('policy', args=[page.slug])}
        if page.slug in {'contact', 'tracking', 'faqs', 'about'} or page.footer_group == 'company' and page.slug not in {'privacy', 'terms', 'cookies'}:
            support.append(item)
        else:
            policies.append(item)
    if not any(item['url'] == reverse('track_order') for item in support):
        support.append({'title': 'Order Tracking', 'url': reverse('track_order')})
    if any(page.slug == 'contact' for page in pages):
        support.append({'title': 'Complaint / Advice', 'url': reverse('policy', args=['contact'])})
    support.extend([{'title': 'Request a Preorder', 'url': reverse('preorder')},
                    {'title': 'Offers & Deals', 'url': reverse('offers')}])
    groups = []
    for group in FooterGroup.objects.filter(visible=True).prefetch_related('categories', 'brands', 'collections'):
        links = [{'title': c.name, 'url': reverse('product_list') + '?' + urlencode({'category': c.pk})}
                 for c in group.categories.all()]
        links += [{'title': b.name, 'url': reverse('product_list') + '?' + urlencode({'brand': b.pk})}
                  for b in group.brands.all()]
        links += [{'title': c.title, 'url': reverse('home_section', args=[c.pk])}
                  for c in group.collections.all() if c.active]
        if links:
            groups.append({'title': group.title, 'links': links})
    social, apps, whatsapp = [], [], None
    hosts = {'facebook.com': 'facebook', 'instagram.com': 'instagram', 'linkedin.com': 'linkedin',
             'youtube.com': 'youtube', 'youtu.be': 'youtube', 'github.com': 'github'}
    for link in business:
        host = urlsplit(link['url']).hostname or ''
        host = host.removeprefix('www.')
        if link['kind'] == 'whatsapp' and host in {'wa.me', 'api.whatsapp.com', 'web.whatsapp.com'}:
            try:
                destination = whatsapp_url(link['url'])
            except ValueError:
                destination = None
            if destination and whatsapp is None:
                whatsapp = {**link, 'url': destination}
        elif link['kind'] == 'social':
            social.append({**link, 'icon': hosts.get(host, 'link')})
        elif link['kind'] in {'app_store', 'google_play'} and host in {'apps.apple.com', 'play.google.com'}:
            apps.append(link)
    return {'footer_support': support, 'footer_policies': policies, 'footer_outlets': public_outlets(),
            'footer_directory': groups, 'footer_profiles': social, 'footer_whatsapp': whatsapp, 'footer_apps': apps}

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.cache import never_cache

from .commerce import pc_build, selected_zone
from .models import Product, ProductQuestion
from .services import settings_for_store, normalized_cart, cart_lines, set_cart


@require_GET
def delivery_quote(request):
    try:
        zone = selected_zone(request.GET.get('zone'))
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    charge = zone.shipping_price if zone else settings_for_store().shipping_price
    return JsonResponse({'area': zone.name if zone else 'Standard delivery', 'shipping': str(charge),
                         'estimate': zone.estimate if zone else 'Delivery time confirmed by the store',
                         'note': 'Estimated after order confirmation; weekends and holidays may affect delivery.'})


@never_cache
@require_http_methods(['GET', 'POST'])
def pc_builder(request):
    data = request.POST if request.method == 'POST' else request.GET
    build = pc_build(data)
    if request.method == 'POST':
        if not build['can_add']:
            messages.error(request, 'Complete your build and resolve the component issues before adding it to your bag.')
            return render(request, 'shop/pc_builder.html', {'build': build}, status=400)
        cart = normalized_cart(request.session)
        try:
            for item in build['chosen'].values():
                cart[item['key']] = cart.get(item['key'], 0) + 1
                if cart[item['key']] > 99:
                    raise ValidationError('The shopping bag quantity limit is 99 per option.')
            cart_lines({'cart': cart}, strict=True)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
            return render(request, 'shop/pc_builder.html', {'build': build}, status=400)
        set_cart(request.session, cart)
        messages.success(request, 'Your selected components are in your shopping bag. Please confirm the remaining compatibility details with the store.')
        return redirect('cart_view')
    if request.GET.get('format') == 'json':
        return JsonResponse({'html': render_to_string('shop/includes/build_summary.html', {'build': build}, request=request)})
    return render(request, 'shop/pc_builder.html', {'build': build})


@login_required
@require_POST
def ask_question(request, pk):
    product = get_object_or_404(Product, pk=pk)
    question = request.POST.get('question', '').strip()
    from datetime import timedelta
    if not 10 <= len(question) <= 1000:
        messages.error(request, 'Write a product question between 10 and 1,000 characters.')
    elif ProductQuestion.objects.filter(user=request.user, created_at__gte=timezone.now() - timedelta(minutes=1)).exists():
        messages.error(request, 'Please wait a minute before asking another question.')
    else:
        ProductQuestion.objects.create(product=product, user=request.user, question=question)
        messages.success(request, 'Your question has been sent to the store. It will appear here after the answer is reviewed.')
    return redirect(reverse('product_detail', args=[pk]) + '#questions')


@require_GET
def sitemap(request):
    paths = [reverse('home'), reverse('product_list'), reverse('pc_builder')]
    paths += [reverse('product_detail', args=[pk]) for pk in Product.objects.values_list('pk', flat=True)]
    body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    body += ''.join(f'<url><loc>{escape(request.build_absolute_uri(path))}</loc></url>' for path in paths)
    return HttpResponse(body + '</urlset>', content_type='application/xml')


@require_GET
def robots(request):
    paths = ['/admin/', '/checkout/', '/cart/', '/profile/', '/order/', '/order-success/', '/payments/', '/internal/']
    text = 'User-agent: *\n' + ''.join(f'Disallow: {path}\n' for path in paths)
    return HttpResponse(text + 'Sitemap: ' + request.build_absolute_uri(reverse('sitemap')) + '\n', content_type='text/plain')

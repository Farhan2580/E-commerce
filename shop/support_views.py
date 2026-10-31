from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods

from .forms import SupportForm
from .models import Category, FAQ, InformationPage, Order, ProductWarranty, SupportRequest
from .services import settings_for_store
from .commerce import accessible_orders, order_progress
from .support import (UI, allow_submission, business_links, faq_answer, form_nonce, language_for,
                      localized, page_content, page_is_public, payment_cards, support_token, warranty_content)


def outlets(request):
    from .footer import public_outlets
    return render(request, 'shop/outlets.html', {'outlets': public_outlets()})


def get_page(request, slug):
    page = get_object_or_404(InformationPage.objects.prefetch_related('sections'), slug=slug)
    preview = request.GET.get('preview') == '1' and request.user.is_staff and request.user.has_perm('shop.view_informationpage')
    if not page_is_public(page) and not preview:
        raise Http404('This information page is not published.')
    return page, bool(preview)


def support_form(request, order=None):
    language = language_for(request)
    scope = f'order:{order.pk}' if order else 'contact'
    initial = {'form_token': support_token(request, scope)}
    if request.user.is_authenticated:
        initial.update(name=request.user.get_full_name(), email=request.user.email)
    form = SupportForm(request.POST if request.method == 'POST' else None, initial=initial,
                       nonce=form_nonce(request), scope=scope, language=language)
    status, saved = 200, None
    if request.method == 'POST':
        try:
            if not allow_submission(request):
                form.add_error(None, UI[language]['rate_error'])
                return form, 429, None
            if form.is_valid():
                data = form.cleaned_data
                saved, _ = SupportRequest.objects.get_or_create(submission_token=data['form_token'], defaults={
                    'name': data['name'], 'phone': data['phone'], 'email': data['email'], 'message': data['message'],
                    'kind': 'order' if order else data['topic'], 'order': order,
                    'user': request.user if request.user.is_authenticated else None, 'language': language})
            else:
                status = 400
        except (IntegrityError, OperationalError):
            form.add_error(None, UI[language]['storage_error'])
            status = 409
    return form, status, saved


@never_cache
@require_http_methods(['GET', 'POST'])
def information(request, slug):
    if slug == 'tracking':
        return track_order(request)
    page, preview = get_page(request, slug)
    if request.method == 'POST' and (slug != 'contact' or preview and page.status != 'published'):
        return HttpResponseNotAllowed(['GET'])
    language = language_for(request)
    store = settings_for_store()
    context = {**page_content(page, language), 'staff_preview': preview, 'business_links': business_links(language)}
    if slug in {'contact', 'payments', 'shipping', 'faqs'} and store.updated_at:
        context['last_updated'] = max(context['last_updated'], store.updated_at)
    if slug == 'contact' and context['business_links']:
        context['last_updated'] = max(context['last_updated'], *(link['updated_at'] for link in context['business_links']))
    status = 200
    if slug == 'contact':
        form, status, saved = support_form(request)
        if saved:
            messages.success(request, f'{UI[language]["received"]} {saved.reference}')
            return redirect('policy', slug='contact')
        context['support_form'] = form
    elif slug == 'faqs':
        query = request.GET.get('q', '').strip()[:200]
        group = request.GET.get('group', '')
        entries = FAQ.objects.filter(status='published')
        if group:
            entries = entries.filter(group=group)
        grouped = {}
        group_bn = {'ordering': 'অর্ডার', 'payments': 'পেমেন্ট', 'delivery': 'ডেলিভারি', 'cancellation': 'বাতিল',
                    'returns': 'রিটার্ন', 'authenticity': 'আসল পণ্য', 'cod': 'ক্যাশ অন ডেলিভারি', 'tracking': 'ট্র্যাকিং', 'support': 'সহায়তা'}
        for entry in entries:
            question, answer = localized(entry, 'question', language), faq_answer(entry, store, language)
            searchable = ' '.join([question, answer, entry.question_en, entry.answer_en])
            if not answer.strip() or query and query.casefold() not in searchable.casefold():
                continue
            context['last_updated'] = max(context['last_updated'], entry.updated_at)
            grouped.setdefault(entry.group, []).append({'question': question, 'answer': answer})
            if language == 'bn' and entry.answer_source == 'text' and not entry.answer_bn:
                context['translation_fallback'] = True
        labels = {key: group_bn[key] if language == 'bn' else label for key, label in FAQ.GROUPS}
        context.update(faq_groups=[{'label': labels[key], 'entries': values} for key, values in grouped.items()],
                       faq_group_options=list(labels.items()), faq_query=query, selected_faq_group=group)
    elif slug == 'payments':
        context['payment_cards'] = payment_cards(store, language)
    elif slug == 'shipping':
        from .models import DeliveryZone
        context['delivery_zones'] = DeliveryZone.objects.filter(active=True)
    elif slug == 'cookies':
        context['cookie_inventory'] = [
            {'name': settings.SESSION_COOKIE_NAME, 'purpose': 'Account sign-in, shopping cart, comparison, browsing history, language and form security state.' if language == 'en' else 'অ্যাকাউন্ট, কার্ট, তুলনা, দেখার ইতিহাস, ভাষা ও ফর্মের নিরাপত্তার তথ্য।', 'days': settings.SESSION_COOKIE_AGE // 86400},
            {'name': settings.CSRF_COOKIE_NAME, 'purpose': 'Protects form submissions against cross-site request forgery.' if language == 'en' else 'অন্য সাইট থেকে অননুমোদিত ফর্ম পাঠানো ঠেকাতে সহায়তা করে।', 'days': settings.CSRF_COOKIE_AGE // 86400},
        ]
    elif slug == 'about':
        context['about_categories'] = Category.objects.filter(parent__isnull=True)
    elif slug == 'warranty':
        query = request.GET.get('q', '').strip()[:200]
        warranties = ProductWarranty.objects.filter(is_verified=True).select_related('product')
        if query:
            warranties = warranties.filter(product__name__icontains=query)
        context.update(warranty_entries=[warranty_content(item, language) for item in warranties[:50]], warranty_query=query)
        if context['warranty_entries']:
            context['last_updated'] = max(context['last_updated'], *(entry['updated_at'] for entry in context['warranty_entries']))
    response = render(request, 'shop/policy.html', context, status=status)
    if status == 429:
        response['Retry-After'] = '3600'
    return response


@never_cache
@require_http_methods(['GET', 'POST'])
def track_order(request, order_id=None):
    if not request.user.is_authenticated and not request.session.get('guest_order_ids'):
        return redirect(reverse('login') + '?next=' + request.path)
    page, preview = get_page(request, 'tracking')
    language = language_for(request)
    orders = accessible_orders(request).order_by('-date_ordered')
    selected = str(order_id or request.GET.get('order', ''))
    order = None
    if selected:
        if not selected.isdigit() or len(selected) > 18:
            raise Http404
        order = get_object_or_404(orders.prefetch_related('status_events'), pk=int(selected))
    if request.method == 'POST' and order is None:
        raise Http404
    context = {**page_content(page, language), 'staff_preview': preview, 'tracking_orders': orders,
               'tracked_order': order, 'document_language': language}
    status = 200
    if order:
        form, status, saved = support_form(request, order)
        if saved:
            messages.success(request, f'{UI[language]["received"]} {saved.reference}')
            return redirect('track_order_detail', order_id=order.pk)
        labels_bn = {'received': 'গৃহীত', 'processing': 'প্রক্রিয়াধীন', 'shipped': 'পাঠানো হয়েছে', 'delivered': 'পৌঁছে দেওয়া হয়েছে', 'cancelled': 'বাতিল'}
        context.update(support_form=form, order_progress=order_progress(order),
                       tracking_status=labels_bn.get(order.status, order.get_status_display()) if language == 'bn' else order.get_status_display(),
                       tracking_events=[{'label': labels_bn.get(event.status, event.get_status_display()) if language == 'bn' else event.get_status_display(),
                                         'created_at': event.created_at} for event in order.status_events.all()])
    response = render(request, 'shop/support_tracking.html', context, status=status)
    if status == 429:
        response['Retry-After'] = '3600'
    return response


@require_POST
def set_support_language(request):
    language = request.POST.get('language', '')
    if language not in UI:
        return HttpResponseBadRequest('This website is available in English.')
    request.session['support_language'] = 'en'
    target = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        target = reverse('policy', args=['contact'])
    return HttpResponseRedirect(target)

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.db import OperationalError, IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from .models import PaymentAttempt
from .payments import initiate, reconcile, retry_payment


@login_required
@require_POST
def start(request, attempt_id):
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user)
    try:
        url = initiate(attempt.pk)
    except (OperationalError, IntegrityError):
        url = ''
    if not url:
        messages.warning(request, 'Hosted payment could not be opened. Check the payment status below before trying again; no successful payment has been confirmed.')
    return redirect(url) if url else redirect('order_detail', order_id=attempt.order_id)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def returned(request, attempt_id):
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id)
    # Browser input is deliberately ignored. Query with our persisted transaction ID.
    try:
        reconcile(attempt.pk)
    except (OperationalError, IntegrityError):
        pass  # Scheduled reconciliation retries; never trust redirect input.
    return redirect('order_detail', order_id=attempt.order_id)


@csrf_exempt
@require_POST
def ipn(request, attempt_id):
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id)
    try:
        reconcile(attempt.pk)
    except (OperationalError, IntegrityError):
        return HttpResponse('Please retry notification', status=503, content_type='text/plain')
    # No customer data or gateway payload is returned. Scheduled reconciliation
    # retries pending results even if the provider never retries this notification.
    return HttpResponse('Acknowledged', content_type='text/plain')


@login_required
@require_POST
def refresh(request, attempt_id):
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user)
    try:
        reconcile(attempt.pk)
    except (OperationalError, IntegrityError):
        messages.warning(request, 'Payment verification is busy. Please check again shortly.')
    return redirect('order_detail', order_id=attempt.order_id)


@login_required
@require_POST
def retry(request, attempt_id):
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user)
    try:
        reconcile(attempt.pk)
        new = retry_payment(attempt.pk, request.user)
        url = initiate(new.pk)
        if url:
            return redirect(url)
        messages.warning(request, 'The provider has not confirmed a new checkout session. Check this order’s payment status before trying again.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    except (OperationalError, IntegrityError):
        messages.warning(request, 'Payment is busy. Check this order’s status before trying again.')
    return redirect('order_detail', order_id=attempt.order_id)


@login_required
@require_POST
def manual_reference(request, attempt_id):
    from .manual_payments import submit_reference
    attempt = get_object_or_404(PaymentAttempt, pk=attempt_id, order__user=request.user, provider='manual_bkash')
    try:
        submit_reference(attempt.pk, request.user, request.POST.get('reference', ''))
        messages.info(request, 'Reference saved. Awaiting verification by the store.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    except (OperationalError, IntegrityError):
        messages.error(request, 'Unable to save the reference. Check this order before submitting it again.')
    return redirect('order_detail', order_id=attempt.order_id)

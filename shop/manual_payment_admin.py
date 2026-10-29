from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .models import ManualPaymentClaim, ManualPaymentAudit
from .manual_payments import review_reference


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[('confirmed', 'Confirm receipt verified in merchant records'), ('rejected', 'Reject reference')])
    transaction_checked = forms.BooleanField(required=False, label='Transaction identity checked in merchant records, not a customer screenshot')
    recipient_checked = forms.BooleanField(required=False, label='Recipient matches this order’s receiving business account')
    amount_checked = forms.BooleanField(required=False, label='Exact amount and BDT currency match this order')
    order_checked = forms.BooleanField(required=False, label='Order reference matches and this receipt has not already been used')
    note = forms.CharField(min_length=10, max_length=2000, widget=forms.Textarea, help_text='Record the merchant source checked and findings. Never record payment secrets.')

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'confirmed' and not all(data.get(key) for key in
                ['transaction_checked', 'recipient_checked', 'amount_checked', 'order_checked']):
            raise forms.ValidationError('Complete every merchant-record check before confirming receipt.')
        return data


class AuditInline(admin.TabularInline):
    model = ManualPaymentAudit
    extra = 0
    readonly_fields = ('actor', 'action', 'note', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ManualPaymentClaim)
class ManualClaimAdmin(admin.ModelAdmin):
    list_display = ('reference', 'attempt', 'status', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('reference',)
    readonly_fields = ('attempt', 'reference', 'status', 'submitted_at', 'review_link')
    inlines = [AuditInline]

    def get_urls(self):
        return [path('<int:object_id>/review/', self.admin_site.admin_view(self.review), name='shop_manualpaymentclaim_review')] + super().get_urls()

    def review_link(self, obj):
        return format_html('<a href="{}">Review merchant receipt</a>', reverse('admin:shop_manualpaymentclaim_review', args=[obj.pk]))

    def review(self, request, object_id):
        if not (self.has_view_permission(request) and request.user.has_perm('shop.verify_manual_payment')
                and request.user.has_perm('shop.change_order')):
            raise PermissionDenied
        claim = get_object_or_404(ManualPaymentClaim.objects.select_related('attempt__order'), pk=object_id)
        form = ReviewForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            try:
                review_reference(claim.pk, request.user, form.cleaned_data['decision'], form.cleaned_data['note'])
            except ValidationError as exc:
                form.add_error(None, ' '.join(exc.messages))
            else:
                self.message_user(request, 'Manual payment review recorded.', messages.SUCCESS)
                return redirect('admin:shop_manualpaymentclaim_change', claim.pk)
        return TemplateResponse(request, 'admin/shop/manual_payment_review.html', {
            **self.admin_site.each_context(request), 'title': 'Verify manual bKash receipt',
            'opts': self.model._meta, 'claim': claim, 'form': form})

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

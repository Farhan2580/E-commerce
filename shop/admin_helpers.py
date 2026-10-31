"""Presentation helpers for connected Admin forms and actionable status filters."""
from django.contrib import admin
from django.db.models import F, Q
from django.urls import reverse


class WorkspaceAdmin(admin.ModelAdmin):
    change_form_template = 'admin/shop/workspace_change_form.html'
    workspace_title = 'Edit store information'
    workspace_description = 'Changes use the same records as the customer storefront.'
    workspace_links = ()
    list_per_page = 30

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        links = [{'label': label, 'url': reverse(url)} for label, url, permission in self.workspace_links
                 if request.user.has_perm(permission)]
        return super().changeform_view(request, object_id, form_url, {
            **(extra_context or {}), 'workspace_title': self.workspace_title,
            'workspace_description': self.workspace_description, 'workspace_links': links})


class InventoryFilter(admin.SimpleListFilter):
    title = 'inventory'
    parameter_name = 'inventory'

    def lookups(self, request, model_admin):
        return [('low', 'Low or out of stock'), ('untracked', 'Untracked stock')]

    def queryset(self, request, queryset):
        if self.value() == 'low':
            return queryset.filter(Q(variants__isnull=True, stock__lte=F('low_stock_threshold')) |
                                   Q(variants__stock__lte=F('low_stock_threshold'))).distinct()
        if self.value() == 'untracked':
            return queryset.filter(variants__isnull=True, stock__isnull=True)
        return queryset


class FulfillmentFilter(admin.SimpleListFilter):
    title = 'work queue'
    parameter_name = 'fulfillment'

    def lookups(self, request, model_admin):
        return [('pending', 'Pending fulfillment'), ('payment', 'Awaiting payment')]

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(status__in=['received', 'confirmed', 'processing', 'packed'])
        if self.value() == 'payment':
            return queryset.filter(status='awaiting_payment')
        return queryset


class OpenClaimFilter(admin.SimpleListFilter):
    title = 'work queue'
    parameter_name = 'open_requests'

    def lookups(self, request, model_admin):
        return [('yes', 'Open requests'), ('no', 'Closed requests')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(status__in=['resolved', 'rejected'])
        if self.value() == 'no':
            return queryset.filter(status__in=['resolved', 'rejected'])
        return queryset

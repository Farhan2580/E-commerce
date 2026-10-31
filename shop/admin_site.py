from django.contrib.admin import AdminSite
from django.db.models import F, Q
from django.urls import reverse
from .admin_navigation import grouped_navigation


def can_view(user, model_name):
    return user.has_perm(f'shop.view_{model_name}') or user.has_perm(f'shop.change_{model_name}')


class StoreAdminSite(AdminSite):
    site_header = 'GadgetFlow'
    site_title = 'GadgetFlow Admin'
    index_title = 'Store overview'
    site_url = '/'

    def each_context(self, request):
        context = super().each_context(request)
        context['store_admin_groups'] = grouped_navigation(context['available_apps'], request.path)
        context['store_admin_tools'] = {
            'operations': request.user.has_perm('shop.view_product') and request.user.has_perm('shop.view_order'),
            'csv': any(request.user.has_perm(f'shop.{action}_{model}') for model in ('brand', 'product', 'productvariant') for action in ('view', 'add', 'change')),
        }
        return context

    def index(self, request, extra_context=None):
        from .models import Product, Order, ServiceClaim, SupportRequest
        stats = []
        if can_view(request.user, 'product'):
            stats.append({'label': 'Products', 'value': Product.objects.count(), 'note': 'Catalog items', 'url': reverse('admin:shop_product_changelist')})
            low = Product.objects.filter(Q(variants__isnull=True, stock__lte=F('low_stock_threshold')) | Q(variants__stock__lte=F('low_stock_threshold'))).distinct().count()
            stats.append({'label': 'Low stock', 'value': low, 'note': 'Products needing a stock check', 'url': reverse('admin:shop_product_changelist') + '?inventory=low', 'attention': low > 0})
        if can_view(request.user, 'order'):
            pending = Order.objects.filter(status__in=['received', 'confirmed', 'processing', 'packed']).count()
            stats.append({'label': 'Pending orders', 'value': pending, 'note': 'Waiting for fulfillment', 'url': reverse('admin:shop_order_changelist') + '?fulfillment=pending'})
        if can_view(request.user, 'serviceclaim'):
            count = ServiceClaim.objects.exclude(status__in=['resolved', 'rejected']).count()
            stats.append({'label': 'Open service requests', 'value': count, 'note': 'Returns and warranty follow-ups', 'url': reverse('admin:shop_serviceclaim_changelist') + '?open_requests=yes'})
        elif can_view(request.user, 'supportrequest'):
            count = SupportRequest.objects.filter(status__in=['new', 'in_progress']).count()
            stats.append({'label': 'Support inbox', 'value': count, 'note': 'New and in-progress enquiries', 'url': reverse('admin:shop_supportrequest_changelist')})
        return super().index(request, {**(extra_context or {}), 'store_admin_stats': stats})

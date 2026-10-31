"""Schedule this command to generate private notifications; --email enables SMTP."""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from shop.models import PriceAlert, StockAlert, CustomerNotification


class Command(BaseCommand):
    help = 'Generate in-account restock/price notifications; optionally send configured emails.'

    def add_arguments(self, parser):
        parser.add_argument('--email', action='store_true')

    def handle(self, *args, **options):
        if options['email'] and not settings.STOCK_ALERT_EMAIL_READY:
            raise CommandError('Configure SMTP and DEFAULT_FROM_EMAIL before using --email.')
        created = 0
        for Model, kind in [(StockAlert, 'stock'), (PriceAlert, 'price')]:
            for pk in Model.objects.filter(active=True).values_list('pk', flat=True).iterator():
                with transaction.atomic():
                    alert = Model.objects.select_for_update().select_related('product', 'variant').get(pk=pk)
                    if not alert.active:
                        continue
                    item = alert.variant or alert.product
                    if item.stock is None or item.stock <= 0 or (not alert.variant and alert.product.has_variants):
                        continue
                    if kind == 'price' and item.price > alert.target_price:
                        continue
                    title = ('Back in stock: ' if kind == 'stock' else 'Price target reached: ') + alert.product.name
                    key = f'{kind}:{pk}:{alert.created_at.isoformat()}'
                    _, new = CustomerNotification.objects.get_or_create(key=key, defaults={
                        'user': alert.user, 'product': alert.product, 'title': title[:250],
                        'message': f'{getattr(item, "option_label", alert.product.name)} is available at BDT {item.price}. Prices and availability can change.'})
                    created += int(new)
                    if kind == 'price':
                        alert.active, alert.triggered_at = False, timezone.now()
                        alert.save(update_fields=['active', 'triggered_at'])
        if options['email']:
            call_command('send_stock_alerts')
            for pk in PriceAlert.objects.filter(triggered_at__isnull=False, email_sent_at__isnull=True).exclude(email='').values_list('pk', flat=True).iterator():
                with transaction.atomic():
                    alert = PriceAlert.objects.select_for_update().select_related('product').get(pk=pk)
                    if alert.email_sent_at:
                        continue
                    url = settings.STOREFRONT_URL + reverse('product_detail', args=[alert.product_id])
                    try:
                        delivered = send_mail('Your GadgetFlow price alert',
                            f'{alert.product.name} reached your target of BDT {alert.target_price}. Check current price and availability: {url}',
                            settings.DEFAULT_FROM_EMAIL, [alert.email], fail_silently=False)
                    except Exception as exc:
                        raise CommandError(f'Price alert {pk} email failed ({type(exc).__name__}); it remains pending.') from exc
                    if delivered != 1:
                        raise CommandError(f'Email was not confirmed for alert {pk}.')
                    alert.email_sent_at = timezone.now()
                    alert.save(update_fields=['email_sent_at'])
        self.stdout.write(f'Created {created} in-account notification(s).')

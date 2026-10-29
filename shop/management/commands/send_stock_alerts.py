"""Run periodically after inventory updates. Only confirmed sends are marked sent."""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from shop.models import StockAlert


class Command(BaseCommand):
    help = 'Send pending alerts for items now in stock. Requires configured SMTP.'

    def handle(self, *args, **options):
        if not settings.STOCK_ALERT_EMAIL_READY:
            raise CommandError('Configure EMAIL_HOST and DEFAULT_FROM_EMAIL (plus SMTP credentials) before sending stock alerts.')
        sent = 0
        for pk in StockAlert.objects.filter(active=True, sent_at__isnull=True).values_list('pk', flat=True).iterator():
            with transaction.atomic():
                alert = StockAlert.objects.select_for_update().select_related('product', 'variant').get(pk=pk)
                if not alert.active or alert.sent_at:
                    continue
                item = alert.variant or alert.product
                # Untracked inventory is not evidence that an item returned to stock.
                if item.stock is None or item.stock <= 0 or (not alert.variant and alert.product.has_variants):
                    continue
                # Acquire a write reservation before sending, including on SQLite.
                if not StockAlert.objects.filter(pk=pk, active=True, sent_at__isnull=True).update(active=False):
                    continue
                name = alert.product.name + (f' / {alert.variant.option_label}' if alert.variant else '')
                url = settings.STOREFRONT_URL + reverse('product_detail', args=[alert.product_id])
                try:
                    delivered = send_mail(f'Back in stock: {name}',
                                          f'{name} is available in the GadgetFlow catalog. Availability may change.\n\nView product: {url}\nManage alerts: {settings.STOREFRONT_URL}/profile/',
                                          settings.DEFAULT_FROM_EMAIL, [alert.email], fail_silently=False)
                except Exception as exc:
                    raise CommandError(f'Email delivery failed for alert {pk}; subscription remains pending ({type(exc).__name__}).') from exc
                if delivered != 1:
                    raise CommandError(f'Email backend did not confirm alert {pk}; subscription remains pending.')
                alert.sent_at = timezone.now()
                alert.active = False
                alert.save(update_fields=['sent_at', 'active'])
                sent += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} stock alert(s).'))

from django.core.management.base import BaseCommand
from shop.models import PaymentAttempt
from shop.payments import reconcile


class Command(BaseCommand):
    help = 'Query sandbox payments and release expired stock reservations. Schedule every minute.'

    def handle(self, *args, **options):
        # Include expired/failed attempts for late settlement detection. Paid attempts
        # are immutable; reviews remain visible for an operator to resolve/refund.
        for pk in PaymentAttempt.objects.exclude(status='paid').values_list('pk', flat=True).iterator():
            reconcile(pk)
        self.stdout.write('Payment reconciliation complete.')

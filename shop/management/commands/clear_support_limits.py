from django.core.management.base import BaseCommand
from django.utils import timezone
from shop.models import SupportRateLimit


class Command(BaseCommand):
    help = 'Delete expired support rate-limit hashes; does not delete customer submissions.'

    def handle(self, *args, **options):
        count, _ = SupportRateLimit.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Removed {count} expired support rate-limit record(s).')

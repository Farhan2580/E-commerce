from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from shop.models import Category, Brand, NavigationItem


class Command(BaseCommand):
    help = 'Preview requested category navigation; --apply adds only missing menu/category records.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        labels = ['Apple Store', 'Phones', 'Tablets', 'Desktop', 'Laptops', 'PC Components',
                  'Gadgets', 'PC Accessories', 'Office Equipment', 'Appliances', 'Lifestyle', 'Security', 'Networking']
        for position, label in enumerate(labels):
            if NavigationItem.objects.filter(label=label).exists():
                self.stdout.write(f'Skip existing: {label}')
                continue
            brand, category = None, None
            if label == 'Apple Store':
                brand = Brand.objects.filter(name__iexact='Apple').first()
                if not brand:
                    raise CommandError('Configure the actual Apple brand first.')
            else:
                # Reuse equivalent existing categories without renaming them.
                target = {'Laptops': 'Laptop', 'Gadgets': 'Smart Tech'}.get(label, label)
                category = Category.objects.filter(name__iexact=target).first()
                if not category:
                    self.stdout.write(f'New empty category: {target}')
                    if options['apply']:
                        category = Category.objects.create(name=target, featured=False)
            self.stdout.write(f'Menu {position + 1}: {label}')
            if options['apply']:
                item = NavigationItem(label=label, category=category, brand=brand, position=position)
                item.full_clean()
                item.save()
        self.stdout.write('Applied.' if options['apply'] else 'Preview only; use --apply to save.')

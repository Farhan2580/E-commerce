"""Create initial footer groups from existing catalog records; never invent catalog data."""
from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Category, Brand, HomeSection, FooterGroup


class Command(BaseCommand):
    help = 'Preview initial catalog footer groups; use --apply to add only missing groups.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        candidates = []
        for title, names in [
            ('Mobile Phones', ['Phones & Tablets', 'Phones', 'Mobile Phones', 'Smartphones']),
            ('Accessories', ['Power', 'Power & Accessories', 'Sound Equipment', 'Audio', 'Watch', 'Accessories']),
            ('Home Appliances', ['Home Appliances']),
        ]:
            categories = list(Category.objects.filter(name__in=names).order_by('position', 'pk'))
            if categories:
                candidates.append((title, 'categories', categories))
        for title in ['Trending', 'Best-selling']:
            collections = list(HomeSection.objects.filter(active=True, title__iexact=title))
            if collections:
                candidates.append((title, 'collections', collections))
        brands = list(Brand.objects.filter(products__isnull=False).distinct())
        if brands:
            candidates.append(('Top Brands', 'brands', brands))
        for position, (title, relation, records) in enumerate(candidates):
            if FooterGroup.objects.filter(title=title).exists():
                self.stdout.write(f'Skip existing group: {title}')
                continue
            self.stdout.write(f'{title}: ' + ', '.join(str(record) for record in records))
            if options['apply']:
                group = FooterGroup.objects.create(title=title, position=position)
                getattr(group, relation).set(records)
        self.stdout.write('Applied missing groups.' if options['apply'] else 'Preview only. Use --apply to save.')

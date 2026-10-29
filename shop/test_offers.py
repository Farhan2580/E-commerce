from datetime import timedelta
from django.template.loader import render_to_string
from django.test import TestCase
from django.utils import timezone
from .models import Offer
from .views import active_offers


class OfferLayoutTests(TestCase):
    def test_included_cards_do_not_create_an_anonymous_grid_item(self):
        offer = Offer.objects.create(title='Offer', description='Offer details', link='/products/')
        html = render_to_string('shop/includes/offer_cards.html', {'offers': [offer]})
        # A U+FEFF from the included file is not whitespace to CSS Grid and
        # consumes a card position despite being invisible to the customer.
        self.assertNotIn('\ufeff', html)
        self.assertTrue(html.lstrip().startswith('<article'))
        self.assertIn('href="/products/"', html)

    def test_display_order_and_id_tie_breaker_are_stable(self):
        Offer.objects.all().delete()  # Isolated test database only.
        iphone = Offer.objects.create(title='iPhone', description='Original iPhone copy', position=0)
        samsung = Offer.objects.create(title='Samsung Galaxy', description='Original Samsung copy', position=0)
        macbook = Offer.objects.create(title='MacBook', description='Original MacBook copy', position=0)
        self.assertEqual(list(active_offers()), [iphone, samsung, macbook])
        macbook.position = 1
        macbook.save(update_fields=['position'])
        iphone.position = 2
        iphone.save(update_fields=['position'])
        self.assertEqual(list(active_offers()), [samsung, macbook, iphone])

    def test_ordering_preserves_active_date_filters_and_content(self):
        now = timezone.now()
        current = Offer.objects.create(title='Current', description='Unchanged offer description',
            starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1), link='/products/')
        future = Offer.objects.create(title='Future', description='Future copy', starts_at=now + timedelta(days=1))
        expired = Offer.objects.create(title='Expired', description='Old copy', ends_at=now - timedelta(days=1))
        disabled = Offer.objects.create(title='Disabled', description='Disabled copy', is_active=False)
        self.assertIn(current, active_offers())
        for excluded in [future, expired, disabled]:
            self.assertNotIn(excluded, active_offers())
        current.refresh_from_db()
        self.assertEqual(current.description, 'Unchanged offer description')
        self.assertEqual(current.starts_at, now - timedelta(days=1))
        self.assertEqual(current.ends_at, now + timedelta(days=1))

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse

from .models import BusinessLink, StoreSettings
from .whatsapp import whatsapp_url, DEFAULT_MESSAGE
from urllib.parse import parse_qs, urlsplit


class WhatsAppTests(TestCase):
    def test_explicit_number_and_encoded_greeting(self):
        for source in ['https://wa.me/8801300972960',
                       'https://api.whatsapp.com/send?phone=8801300972960']:
            result = whatsapp_url(source)
            self.assertEqual(urlsplit(result).path, '/8801300972960')
            self.assertEqual(parse_qs(urlsplit(result).query)['text'], [DEFAULT_MESSAGE])
        message = 'Hello & help? বাংলা'
        from urllib.parse import urlencode
        self.assertEqual(parse_qs(urlsplit(whatsapp_url('https://wa.me/8801300972960?' +
                         urlencode({'text': message}))).query)['text'], [message])

    def test_unverified_or_invalid_destination_never_falls_back_to_store_phone(self):
        store = StoreSettings.objects.get(pk=1)
        store.phone = '01300972969'
        store.save()
        link = BusinessLink.objects.create(kind='whatsapp', label_en='WhatsApp', url='https://wa.me/01300972969', is_verified=True)
        self.assertNotContains(self.client.get(reverse('home')), 'class="gf-whatsapp-shortcut"')
        link.url, link.is_verified = 'https://wa.me/8801300972960', False
        link.save()
        self.assertNotContains(self.client.get(reverse('home')), 'class="gf-whatsapp-shortcut"')
        link.is_verified = True
        link.image = 'business_profiles/contact.png'
        link.save()
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="gf-whatsapp-shortcut"', count=1)
        self.assertContains(response, 'business_profiles/contact.png')
        self.assertContains(response, 'Dismiss WhatsApp shortcut')

    def test_guarded_import_is_repeatable_and_preserves_target_edits(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'widget.json'
            BusinessLink.objects.create(kind='whatsapp', label_en='WhatsApp', url='https://wa.me/8801300972960', is_verified=True)
            call_command('whatsapp_transfer', export_path=str(bundle), stdout=StringIO())
            BusinessLink.objects.filter(kind='whatsapp').delete()
            def preview():
                output = StringIO()
                call_command('whatsapp_transfer', str(bundle), stdout=output)
                return json.loads(output.getvalue())
            plan = preview()
            self.assertEqual(plan['action'], 'create')
            self.assertFalse(BusinessLink.objects.exists())
            with self.assertRaises(CommandError):
                call_command('whatsapp_transfer', str(bundle), apply=True, stdout=StringIO())
            for index in range(2):
                call_command('whatsapp_transfer', str(bundle), apply=True,
                             expected_plan=preview()['plan_sha256'], production_backup_verified=True,
                             backup=str(root / f'before-{index}.json'), stdout=StringIO())
            self.assertEqual(BusinessLink.objects.count(), 1)
            self.assertEqual(json.loads((root / 'before-0.json').read_text())['records'], [])
            link = BusinessLink.objects.get()
            link.url = 'https://wa.me/8801700000000'
            link.save()
            self.assertEqual(preview()['action'], 'preserve_existing')
            with self.assertRaises(CommandError):
                call_command('whatsapp_transfer', str(bundle), apply=True,
                             expected_plan=preview()['plan_sha256'], production_backup_verified=True,
                             backup=str(root / 'conflict.json'), stdout=StringIO())
            link.refresh_from_db()
            self.assertEqual(link.url, 'https://wa.me/8801700000000')

    def test_stale_plan_and_missing_portrait_cannot_create_rows(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fields = {'label_en': 'WhatsApp', 'label_bn': '', 'url': 'https://wa.me/8801300972960',
                      'image': 'business_profiles/missing-original.png', 'is_verified': True, 'position': 0}
            bundle = root / 'widget.json'
            bundle.write_text(json.dumps({'format': 'gadgetflow-whatsapp-v1', 'fields': fields, 'images': []}))
            output = StringIO()
            call_command('whatsapp_transfer', str(bundle), stdout=output)
            for digest in ['stale', json.loads(output.getvalue())['plan_sha256']]:
                with self.assertRaises(CommandError):
                    call_command('whatsapp_transfer', str(bundle), apply=True, expected_plan=digest,
                                 production_backup_verified=True, backup=str(root / 'before.json'), stdout=StringIO())
            self.assertFalse(BusinessLink.objects.exists())
            self.assertFalse((root / 'before.json').exists())

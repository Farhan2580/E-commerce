from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from djangoProject13.configuration import database_configuration
from .checks import production_database, production_debug


class DeploymentConfigurationTests(SimpleTestCase):
    def test_local_database_stays_local_without_url(self):
        result = database_configuration({}, Path('/workspace'))
        self.assertEqual(result['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(result['NAME'], Path('/workspace/db.sqlite3'))

    def test_database_url_selects_postgres_with_tls(self):
        result = database_configuration({'DATABASE_URL': 'postgresql://fixture:fixture@db.example.test/catalog', 'DATABASE_USE_URL': '1'}, Path('/workspace'))
        self.assertEqual(result['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(result['HOST'], 'db.example.test')
        self.assertEqual(result['OPTIONS']['sslmode'], 'require')
        self.assertTrue(result['CONN_HEALTH_CHECKS'])

    def test_existing_ignored_database_url_does_not_silently_switch_database(self):
        result = database_configuration({'DATABASE_URL': 'postgresql://fixture:fixture@db.example.test/catalog'}, Path('/workspace'))
        self.assertEqual(result['ENGINE'], 'django.db.backends.sqlite3')

    def test_render_rejects_sqlite_and_debug(self):
        with patch.dict('os.environ', {'RENDER': 'true'}), override_settings(DEBUG=True):
            self.assertEqual(production_database(None)[0].id, 'shop.E002')
            self.assertEqual(production_debug(None)[0].id, 'shop.E003')

"""Environment-backed database selection shared by settings and tests."""
from pathlib import Path

import dj_database_url


def database_configuration(environment, base_dir):
    url = environment.get('DATABASE_URL', '').strip()
    # The previous deployment ignored DATABASE_URL. Do not silently switch its
    # database during an automatic code deploy before its data has been backed up.
    if url and environment.get('DATABASE_USE_URL', '0') == '1':
        return dj_database_url.parse(
            url, conn_max_age=600, conn_health_checks=True,
            ssl_require=environment.get('DATABASE_SSL_REQUIRE', '1') == '1',
        )
    return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': Path(base_dir) / 'db.sqlite3'}

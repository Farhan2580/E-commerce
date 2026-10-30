#!/usr/bin/env bash
set -euo pipefail
export DJANGO_SETTINGS_MODULE=djangoProject13.settings
python manage.py check --deploy --tag files --tag database --tag security
# Never silently create/reseed a production database at startup. After a verified
# backup, apply reviewed migrations in the pre-deploy step or Render Shell.
python manage.py migrate --check
exec gunicorn djangoProject13.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --access-logfile - --error-logfile -

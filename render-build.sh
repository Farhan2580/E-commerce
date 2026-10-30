#!/usr/bin/env bash
set -euo pipefail
export DJANGO_SETTINGS_MODULE=djangoProject13.settings
python -m pip install -r requirements.txt
# These are application assets, never uploaded media.
python manage.py collectstatic --noinput

#!/bin/bash

source /opt/TELEGRAM-CRON/.venv/bin/activate
pip install --no-cache -q -r requirements/web.txt
gunicorn --workers 3 --bind 0.0.0.0:7878 wsgi:app # Или waitress-serve --port=7878 wsgi:app


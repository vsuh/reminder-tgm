#!/bin/bash
source /path/to/your/venv/bin/activate
gunicorn --workers 3 --bind 0.0.0.0:7878 wsgi:app # Или waitress-serve --port=7878 wsgi:app

#!/bin/bash

if [ -f ./.env ]; then
  source ./.env
else
  source env/.env.dev
fi;

export FLASK_APP=wsgi:app
export FLASK_PORT=${TLCR_FLASK_PORT}

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi;

source .venv/bin/activate

pip install --no-cache -q -r requirements/rund.txt

mkdir -p ${TLCR_LOGPATH}
touch ${TLCR_LOGPATH}/gunicorn-access.log ${TLCR_LOGPATH}/gunicorn-error.log
chown -R appuser:appuser ${TLCR_LOGPATH}

PYTHONUNBUFFERED=1 exec gunicorn -c gunicorn.conf.py ${FLASK_APP}


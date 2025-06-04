#!/bin/bash

if [ -f ./.env ]; then
  source ./.env
else
  source env/.env.dev
fi;

export FLASK_APP=wsgi:app
export FLASK_PORT=7878

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi;

source .venv/bin/activate

pip install --no-cache -q -r requirements/rund.txt

mkdir -p ${TLCR_LOGPATH}
touch ${TLCR_LOGPATH}/gunicorn-access.log ${TLCR_LOGPATH}/gunicorn-error.log
chown -R appuser:appuser ${TLCR_LOGPATH}

# Запускаем gunicorn с явными настройками логирования
PYTHONUNBUFFERED=1 gunicorn \
#    --access-logfile ${TLCR_LOGPATH}/gunicorn-access.log \
#    --error-logfile ${TLCR_LOGPATH}/gunicorn-error.log \
#    --log-level debug \
#    --capture-output \
#    --enable-stdio-inheritance \
#    -w 2 \
#    -b 0.0.0.0:${FLASK_PORT} \
#    ${FLASK_APP} 


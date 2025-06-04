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

echo $(date)" Test log message" > /workspaces/cron-tg-docker/log/test.log

#gunicorn -c gunicorn.conf.py \
#         --access-logfile log/gunicorn-access.log \
#         --error-logfile log/gunicorn-error.log \
#         --log-level debug \
#         -w 2 -b 0.0.0.0:${FLASK_PORT} ${FLASK_APP} 

gunicorn -c gunicorn.conf.py

# или для windows
#waitress-serve --port=${FLASK_PORT} ${FLASK_APP}

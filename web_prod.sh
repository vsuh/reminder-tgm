#!/bin/bash
source env/.env.dev
export FLASK_APP=wsgi:app

if [ -z "$FLASK_PORT" ]; then
    echo "Error: FLASK_PORT is not set. Please set the FLASK_PORT environment variable."
    exit 1
fi

#gunicorn -w 4 -b 0.0.0.0:${FLASK_PORT} ${FLASK_APP}
# или
waitress-serve --port=${FLASK_PORT} ${FLASK_APP}

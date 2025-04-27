#!/bin/bash
source env/.env.dev
export FLASK_APP=wsgi:app
export FLASK_ENV=development
if [ -z "$FLASK_PORT" ]; then
    echo "Error: FLASK_PORT is not set. Please set the FLASK_PORT environment variable."
    exit 1
fi

flask run -p $FLASK_PORT
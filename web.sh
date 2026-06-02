#!/bin/bash
source env/.env.dev
export FLASK_APP=wsgi:app
export FLASK_ENV=development
export FLASK_PORT=${TLCR_FLASK_PORT}


flask run -p $FLASK_PORT
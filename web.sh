#!/bin/bash
source env/.env.dev
export FLASK_APP=wsgi:app
export FLASK_ENV=development
export FLASK_PORT=7878


flask run -p $FLASK_PORT
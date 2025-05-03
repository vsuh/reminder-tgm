#!/bin/bash
export TELEGRAM_CRON_ROOT=/opt/TELEGRAM-CRON

if [ ! -d ${TELEGRAM_CRON_ROOT} ]; then
  exit 3
fi;

cd ${TELEGRAM_CRON_ROOT}

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi;


source .venv/bin/activate

pip install --no-cache -q -r requirements/rund.txt
python run.py



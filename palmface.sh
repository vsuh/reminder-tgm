#!/bin/bash
myDIR=/home/vsuh/my/projects/reminder

cd ${myDIR}
source ./venv/bin/activate
pip install --upgrade pip
pip install -q -r requirements.txt
gunicorn --workers 2 --bind=0.0.0.0:7878 \
	 --access-logfile /var/log/tg_reminder/access.log \
	 --error-logfile /var/log/tg_reminder/error.log \
	   app:app 


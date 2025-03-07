#!/bin/bash
myDIR=/home/vsuh/my/projects/reminder
cd ${myDIR}
source ./venv/bin/activate
pip install --upgrade pip
pip install -q -r /home/vsuh/my/projects/reminder/requirements.txt
gunicorn --bind=0.0.0.0:7878 app:app 


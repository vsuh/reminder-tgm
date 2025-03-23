import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import date, datetime, timedelta

import pytz
from croniter import croniter
from dateutil.relativedelta import relativedelta
from flask import (Flask, abort, g, jsonify, redirect, render_template,
                   request, send_file, url_for)

from lib.cron_utils import VCron
from lib.db_utils import (add_schedule, delete_schedule, get_schedule,
                           get_schedules, init_db, update_schedule)
from lib.utils import MyError, get_environment, init_log, load_env

# Load environment variables
environment = get_environment()
load_env(environment)

# Read environment variables
TIMEZONE = os.getenv("reminderTZ", "UTC")
DB_PATH = os.getenv("DB_PATH", "settings.db")
LOGPATH = os.getenv("LOGPATH", ".")
LOGLEVEL = os.getenv("LOG_LEVEL", 'INFO').upper()
APIPORT = os.getenv("PORT", "7878")
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", False).lower() in ('true', 'yes', '1')

myVCron = VCron(TIMEZONE)

log = init_log('svrm', LOGPATH, LOGLEVEL)

# Initialize Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG


init_db(DB_PATH, False)

# Функции работы с БД
def get_schedules():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules")
            return [{"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписаний: %s", str(e))
        return []

def get_schedule(schedule_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier, last_fired FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3], "last_fired": row[4]}
            else:
                return None
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписания: %s", str(e))
        return []

def add_schedule(cron, message, modifier):
    if not myVCron.valid(cron):
        raise ValueError(f'Invalid CRON expression: "{cron}"')
    if not myVCron.is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO schedules (cron, message, modifier) VALUES (?, ?, ?)", (cron, message, modifier))
            conn.commit()
            log.info("Добавлено новое расписание: %s, %s, %s", cron, message, modifier)
    except sqlite3.Error as e:
        log.error("Ошибка при добавлении расписания: %s", str(e))

def delete_schedule(schedule_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            conn.commit()
            log.info("Удалено расписание с ID: %d", schedule_id)
    except sqlite3.Error as e:
        log.error("Ошибка при удалении расписания: %s", str(e))

def update_schedule(schedule_id, cron, message, modifier) -> MyError or None:
    if not myVCron.valid(cron):
        log.error(f'Invalid CRON expression: "{cron}"')
        return MyError(f'Invalid CRON expression: "{cron}"') 
    if not myVCron.is_valid_modifier(modifier):
        log.error(f'Invalid modifier expression "{modifier}"')
        return MyError(f'Invalid modifier expression "{modifier}"') 

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET cron = ?, message = ?, modifier = ? WHERE id = ?", (cron, message, modifier, schedule_id))
            conn.commit()
            log.info("Обновлено расписание с ID: %d", schedule_id)
        return None
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении расписания: %s", str(e))

# Эндпоинты Flask API

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cron = request.form.get("cron")
        message = request.form.get("message")
        modifier = request.form.get("modifier", "")
        if not cron or not message:
            abort(400, description="Все поля должны быть заполнены")
        try:
            add_schedule(cron, message, modifier)
        except ValueError as e:
            return render_template("error.html", text=str(e)), 400 # Обработка неверного ввода
        return redirect(url_for("index"))

   
    schedules = []
    for item in get_schedules():
        next_match = myVCron.get_next_match(item['cron'], item['modifier'])
        schedules.append({**item, 'next': next_match.isoformat() if next_match else None})
    return render_template("index.html", schedules=schedules)


@app.route("/schedules", methods=["GET"])
def list_schedules():
    return jsonify(get_schedules())

@app.route("/schedules_all", methods=["POST"])
def create_schedules_by_list():
    list_data = request.get_json()
    if isinstance(list_data, list):
        if len(list_data)==0:
            abort(400, description="Получен пустой массив")
    else:
        abort(400, description="Ожидался массив расписаний")
         
    for data in list_data:
        if not data or "cron" not in data or "message" not in data:
            abort(400, description="Неверный формат данных")
        if not myVCron.valid(data["cron"]):
            raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
        if not myVCron.is_valid_modifier(data.get("modifier", "")):
            raise ValueError(f'Invalid modifier expression "{data.get("modifier", "")}"')

        add_schedule(data["cron"], data["message"], data.get("modifier", ""))
    
    return jsonify({"status": "success"}), 201


@app.route("/schedules", methods=["POST"])
def create_schedule():
    data = request.get_json()
    if not data or "cron" not in data or "message" not in data:
        abort(400, description="Неверный формат данных")

    if not myVCron.valid(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    if not myVCron.is_valid_modifier(data.get("modifier", "")):
        raise ValueError(f'Invalid modifier expression "{data.get("modifier", "")}"')

    add_schedule(data["cron"], data["message"], data.get("modifier", ""))
    return jsonify({"status": "success"}), 201

@app.route("/schedules/<int:schedule_id>", methods=["DELETE"])
def remove_schedule(schedule_id):
    delete_schedule(schedule_id)
    return jsonify({"status": "deleted"})

@app.route('/schedules/<int:schedule_id>/delete', methods=['POST'])
def delete_schedule_post(schedule_id):
    delete_schedule(schedule_id)
    return redirect(url_for('index'))

@app.route("/schedules/<int:schedule_id>", methods=["POST"])
def edit_schedule(schedule_id):
    data = request.get_json()
    if not data or "cron" not in data or "message" not in data:
        abort(400, description="Неверный формат данных")
    cron = data["cron"]
    message = data["message"]
    modifier = data["modifier"]

    if not myVCron.valid(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    modifier = data.get("modifier", "")
    if not myVCron.is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')
    
    update_result = update_schedule(schedule_id, cron, message, modifier)
    return (redirect(url_for("index")) if update_result is None else render_template("error.html", text=str(update_result)))

@app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit_schedule_route(schedule_id):
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)

    if request.method != "POST":
        return render_template("edit.html", schedule=schedule)
    cron = request.form.get("cron")
    message = request.form.get("message")
    modifier = request.form.get("modifier", "")
    if not cron or not message:
        abort(400, description="Все поля должны быть заполнены")
    update_result = update_schedule(schedule_id, cron, message, modifier)
    return (redirect(url_for("index")) if update_result is None else render_template("error.html", text=str(update_result)))


@app.route('/list/<int:schedule_id>', methods=['GET'])
def list_nexts(schedule_id):
    NEXT = 5
    schedule = get_schedule(schedule_id)
    if schedule is None:
        abort(404)

    next_dates = []
    cron_expression = schedule['cron']
    modifier = schedule.get('modifier')
    current_time = datetime.now(tz=myVCron.timezone) # Add timezone to current_time

    for _ in range(NEXT):
        next_match = myVCron.get_next_match(cron_expression, modifier, start_time=current_time)
        if next_match is None:
            break  # Прекращаем, если больше нет совпадений
        next_dates.append(next_match.isoformat())
        current_time = next_match + timedelta(seconds=1) # Add one second to avoid same match

    return render_template("list.html", next_dates=next_dates, schedule=schedule)

from flask import send_file

@app.route('/export', methods=['GET'])
def export_json():
    schedules = get_schedules()
    json_data = json.dumps(schedules, indent=4, ensure_ascii=False)
    with tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.json') as temp_file:
        temp_file.write(json_data)
        temp_file.flush()

    return send_file(
        temp_file.name, 
        mimetype='application/json', 
        as_attachment=True, 
        download_name='schedules_export.json'
    )

@app.route("/drop_db", methods=["GET"])
def reset_db():
    global DB_PATH
    try:
        init_db(DB_PATH)
        return redirect(url_for("index"))

    except Exception as e:
        log.error("Ошибка при переинициализации БД: %s", str(e))
        abort(500, description="Ошибка при переинициализации БД")


@app.template_filter('fromisoformat')
def fromisoformat_filter(s):
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):  # Handle cases where s is None or not a valid ISO string
        return None

@app.template_filter('format_datetime')
def format_datetime_filter(dt):
    return dt.strftime('%Y-%m-%d %H:%M') if dt else "##" # Handle None values


if __name__ == "__main__":
    log.info(f"Запуск Flask-сервера: http://localhost:{APIPORT}")
    app.run(host="0.0.0.0", port=APIPORT)

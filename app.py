import json
import os
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_file
from pathlib import Path as pt
import tempfile
from croniter import croniter
from datetime import datetime
import re

class MyError(Exception):
    pass


ENVIRONMENT = 'prod' if os.name == 'posix' else 'dev'
dotenv = f'.env.{ENVIRONMENT}'
if not pt(dotenv).exists():
    raise MyError(f"file {dotenv} not found")

load_dotenv(dotenv)

TIMEZONE = os.getenv("reminderTZ", "UTC")
DB_PATH = os.getenv("DB_PATH", "settings.db")
LOGPATH = os.getenv("LOGPATH", ".")
APIPORT = os.getenv("PORT", "7878")

# Настройка логирования
def init_log(name: str):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    
    handler2file = RotatingFileHandler(pt(LOGPATH).joinpath(f'{name}.log'), encoding="utf-8", maxBytes=50000, backupCount=5)
    handler2file.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler2file.setFormatter(formatter)
    
    handler2con = logging.StreamHandler()
    handler2con.setLevel(logging.INFO)

    log.addHandler(handler2file)
    log.addHandler(handler2con)
    return log

log = init_log('svrm')

# Инициализация Flask
app = Flask(__name__)

# Инициализация базы данных
def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA encoding = 'UTF-8';")
            cursor.execute('''CREATE TABLE IF NOT EXISTS schedules (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                cron TEXT NOT NULL,
                                message TEXT NOT NULL,
                                modifier TEXT
                            )''')
            conn.commit()
        log.info("База данных успешно инициализирована")
    except sqlite3.Error as e:
        log.error("Ошибка инициализации БД: %s", str(e))

init_db()
def is_valid_cron(expr):
    try:
        return croniter.is_valid(expr)
    except ValueError:
        return False

def is_valid_modifier(modifier):
    if not modifier:
        return True
    pattern = r'^(?:(?P<date>\d{8})>?)?(?P<period>[wdm]\/\d+)$'
    
    match = re.match(pattern, modifier)
    if not match:
        return False
    
    date_part = match.group('date')
    period_part = match.group('period')
    
    # Проверка даты (если указана)
    if date_part:
        try:
            year = int(date_part[:4])
            month = int(date_part[4:6])
            day = int(date_part[6:])
            
            # Проверка на корректность даты
            if not (1900 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31):
                return False
        except ValueError:
            return False
    
    # Проверка периода
    period_match = re.match(r'[wdm]\/\d+$', period_part)
    return bool(period_match)

# Функции работы с БД
def get_schedules():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier FROM schedules")
            return [{"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3]} for row in cursor.fetchall()]
    except sqlite3.Error as e:
        log.error("Ошибка при получении расписаний: %s", str(e))
        return []

def add_schedule(cron, message, modifier):
    if not is_valid_cron(cron):
        raise ValueError(f'Invalid CRON expression: "{cron}"')
    if not is_valid_modifier(modifier):
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

def update_schedule(schedule_id, cron, message, modifier):
    if not is_valid_cron(cron):
        raise ValueError(f'Invalid CRON expression: "{cron}"')
    if not is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE schedules SET cron = ?, message = ?, modifier = ? WHERE id = ?", (cron, message, modifier, schedule_id))
            conn.commit()
            log.info("Обновлено расписание с ID: %d", schedule_id)
    except sqlite3.Error as e:
        log.error("Ошибка при обновлении расписания: %s", str(e))

# Эндпоинты Flask API
@app.route("/schedules", methods=["GET"])
def list_schedules():
    return jsonify(get_schedules())

@app.route("/schedules", methods=["POST"])
def create_schedule():
    data = request.get_json()
    if not data or "cron" not in data or "message" not in data:
        abort(400, description="Неверный формат данных")

    if not is_valid_cron(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    if not is_valid_modifier(data.get("modifier", "")):
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
    if not is_valid_cron(data["cron"]):
        raise ValueError(f'Invalid CRON expression: "{data["cron"]}"')
    modifier = data.get("modifier", "")
    if not is_valid_modifier(modifier):
        raise ValueError(f'Invalid modifier expression "{modifier}"')

    update_schedule(schedule_id, data["cron"], data["message"], modifier)
    return jsonify({"status": "updated"})


@app.route("/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit_schedule_route(schedule_id):
    if request.method == "POST":
        cron = request.form.get("cron")
        message = request.form.get("message")
        modifier = request.form.get("modifier", "")
        if not cron or not message:
            abort(400, description="Все поля должны быть заполнены")
        update_schedule(schedule_id, cron, message, modifier)
        return redirect(url_for("index"))

    schedule = next((s for s in get_schedules() if s['id'] == schedule_id), None)
    if schedule is None:
        abort(404)
    return render_template("edit.html", schedule=schedule)

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
    try:
        os.remove(DB_PATH)
        init_db()
        log.info("База данных переинициализирована")
        return redirect(url_for("index"))
    except Exception as e:
        log.error("Ошибка при переинициализации БД: %s", str(e))
        abort(500, description="Ошибка при переинициализации БД")

@app.errorhandler(ValueError)
def handle_value_error(error):
    return render_template('error.html', text=error.args[0]), 400

# Веб-интерфейс
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        cron = request.form.get("cron")
        message = request.form.get("message")
        modifier = request.form.get("modifier", "")
        if not cron or not message:
            abort(400, description="Все поля должны быть заполнены")
        add_schedule(cron, message, modifier)
        return redirect(url_for("index"))
    return render_template("index.html", schedules=get_schedules())

if __name__ == "__main__":
    log.info(f"Запуск Flask-сервера: http://localhost:{APIPORT}")
    app.run(host="0.0.0.0", port=APIPORT)

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
from datetime import date, datetime, timedelta
import pytz
from dateutil.relativedelta import relativedelta
import re

# Класс для кастомных исключений
class MyError(Exception):
    pass

class VCron:
    def __init__(self, timezone: str = "UTC"):
        self.timezone = pytz.timezone(timezone)

    def check_cron(self, cron_expression: str, date: datetime) -> bool:
        return croniter.match(cron_expression, date)

    def valid(self, cron_expression: str) -> bool:
        try:
            croniter(cron_expression)  # Directly check with croniter
            return True
        except ValueError:
            return False
        
    def is_valid_modifier(self, modifier):
        if not modifier:
            return True
        pattern = r'^(?:(?P<date>\d{8})>?)?(?P<period>[wd]\/\d+)$'

        match = re.match(pattern, modifier)
        if not match:
            return False

        period_part = match['period']

        if date_part := match['date']:
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
        period_match = re.match(r'[wd]\/\d+$', period_part)
        return bool(period_match)

    def check_modifier(self, modifier: str, now: datetime) -> bool:
        if not modifier:
            return True

        parts = modifier.split(">")
        start_date_str = parts[0] if len(parts) == 2 else "20010101"
        rule = parts[-1]

        try:
            start_datetime = self.timezone.localize(datetime.combine(datetime.strptime(start_date_str, "%Y%m%d").date(), datetime.min.time()))
        except OverflowError:
            start_datetime = self.timezone.localize(datetime(2001, 1, 1)) # Fallback to a safe date

        if rule.startswith(("w/", "d/", "m/")):  # Handle all three types
            interval = int(rule[2:])
            delta = relativedelta(now, start_datetime)
            days_since = self.days_since(now.date(), start_datetime.date(), )

            if rule.startswith("w/"):
                weeks = int(days_since/7)
                return (weeks % interval == 0) and (days_since%7 == 0)
            elif rule.startswith("d/"):
                return days_since % interval == 0

        return False
    
    def days_since(self, today_date:datetime.date, base_date: datetime.date) -> int:
        delta = today_date - base_date
        return delta.days

    def get_next_match(self, cron_expression: str, modifier: str = None, start_time: datetime = None) -> datetime or None:
        current_time = start_time or datetime.now(tz=self.timezone)  # Use timezone-aware datetime
        iterator = croniter(cron_expression, current_time)

        for _ in range(9999):  # Limit to prevent infinite loop
            next_match = iterator.get_next(datetime)
            if self.check_modifier(modifier, next_match):
                return next_match.astimezone(self.timezone)  # Ensure correct timezone

        return None
    
# Определение окружения
ENVIRONMENT = 'prod' if os.name == 'posix' else 'dev'
dotenv_path = f'.env.{ENVIRONMENT}'
if not pt(dotenv_path).exists():
    raise MyError(f"Файл {dotenv_path} не найден")

# Загрузка переменных окружения
load_dotenv(dotenv_path)

# Чтение переменных окружения
TIMEZONE = os.getenv("reminderTZ", "UTC")
DB_PATH = os.getenv("DB_PATH", "settings.db")
LOGPATH = os.getenv("LOGPATH", ".")
LOGLEVEL = os.getenv("LOG_LEVEL", 'INFO').upper()
APIPORT = os.getenv("PORT", "7878")
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", False).lower() in ('true', 'yes', '1')

myVCron = VCron(TIMEZONE)

# Настройка логирования
def init_log(name: str):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    try:
        level = getattr(logging, LOGLEVEL)
    except AttributeError:
        level = logging.INFO if ENVIRONMENT == 'prod' else logging.DEBUG
    
    handler2file = RotatingFileHandler(pt(LOGPATH).joinpath(f'{name}.log'), encoding="utf-8", maxBytes=50000, backupCount=5)
    handler2file.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler2file.setFormatter(formatter)
    
    handler2con = logging.StreamHandler()
    handler2con.setLevel(level)

    log.addHandler(handler2file)
    log.addHandler(handler2con)
    return log

log = init_log('svrm')

# Инициализация Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG

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
        log.info(f"База данных '{DB_PATH}' успешно инициализирована")
    except sqlite3.Error as e:
        log.error(f"Ошибка инициализации БД '{DB_PATH}': %s", str(e))

init_db()

# Валидация CRON выражения
# def is_valid_cron(expr):
#     try:
#         return myVCron.valid(expr)
#     except ValueError:
#         return False

# Валидация модификатора
# def is_valid_modifier(modifier):
#     if not modifier:
#         return True
#     pattern = r'^(?:(?P<date>\d{8})>?)?(?P<period>[wd]\/\d+)$'
    
#     match = re.match(pattern, modifier)
#     if not match:
#         return False
    
#     date_part = match.group('date')
#     period_part = match.group('period')
    
#     # Проверка даты (если указана)
#     if date_part:
#         try:
#             year = int(date_part[:4])
#             month = int(date_part[4:6])
#             day = int(date_part[6:])
            
#             # Проверка на корректность даты
#             if not (1900 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 31):
#                 return False
#         except ValueError:
#             return False
    
#     # Проверка периода
#     period_match = re.match(r'[wd]\/\d+$', period_part)
#     return bool(period_match)

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

def get_schedule(schedule_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, cron, message, modifier FROM schedules WHERE id = ?", (schedule_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "cron": row[1], "message": row[2], "modifier": row[3]}
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
    try:
        os.remove(DB_PATH)
        init_db()
        log.info("База данных переинициализирована")
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
    return dt.strftime('%Y-%m-%d %H:%M') if dt else None # Handle None values


if __name__ == "__main__":
    log.info(f"Запуск Flask-сервера: http://localhost:{APIPORT}")
    app.run(host="0.0.0.0", port=APIPORT)
